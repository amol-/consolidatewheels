from __future__ import annotations

import itertools
import os
import pathlib
import tempfile

import pkg_resources
import pkginfo

from . import wheelsfunc


def dedupe(wheels: list[str], destdir: str, mangled: bool = False) -> list[str]:
    """Given a list of wheels remove duplicated libraries

    This searches .dylibs embedded by delocate for libraries
    that have been included multiple times across the wheels
    and will preserve only one of the copies.
    """
    wheels = [os.path.abspath(w) for w in wheels]
    distributions, dependency_tree = build_dependencies_tree(wheels)
    sorted_distributions = sort_dependencies(dependency_tree)
    wheels = [distributions[distname] for distname in sorted_distributions]
    print(wheels)
    with tempfile.TemporaryDirectory() as tmpcd:
        print(f"Dedupe, Working inside {tmpcd}")
        wheeldirs = wheelsfunc.unpackwheels(wheels, workdir=tmpcd)
        delete_duplicate_libs(wheeldirs, mangled)
        wheels = wheelsfunc.packwheels(wheeldirs, destdir)
    return wheels


def build_dependencies_tree(
    wheels: list[str],
) -> tuple[dict[str, str], dict[str, list[str]]]:
    """Given a list of wheels, return how they depend on each other.

    Returns a tuple where the first entry is a dictionary
    containing the mapping of each wheel distribution to the wheel name.
    The second entry is a mapping of each wheel to its own dependencies.
    """
    deptree = {}  # type: dict[str, list[str]]
    name2file = {}

    for wheel_fname in wheels:
        distribution_name, _ = os.path.basename(wheel_fname).split("-", 1)
        name2file[distribution_name] = wheel_fname
        dependencies = deptree[distribution_name] = []

        metadata = pkginfo.get_metadata(wheel_fname)
        print("METADATA", wheel_fname, metadata, metadata.requires_dist)
        deps = metadata.requires_dist
        for req_str in deps:
            req = pkg_resources.Requirement.parse(req_str)
            req_short, _sep, _marker = str(req).partition(";")
            if req.marker is None:
                # unconditional dependency, track it.
                dependencies.append(req_short)
                continue

    return name2file, deptree


def sort_dependencies(deptree: dict[str, list[str]]) -> list[str]:
    """Given a wheels dependency tree, sort wheels based on their dependencies.

    This sorts the output of ``build_dependencies_tree`` so that wheels
    that have no dependencies on other wheels are first, and then
    dependants come subsequently
    """
    result = []
    tracked_deps = set(deptree.keys())
    while deptree:
        for dname, dreqs in list(deptree.items()):
            if not dreqs:
                # No dependencies at all, order won't matter.
                result.append(dname)
                deptree.pop(dname)
                continue

            dreqs_set = set(dreqs)
            if not dreqs_set & tracked_deps:
                # There are no dependencies that we have to consolidate
                # the order won't matter
                result.append(dname)
                deptree.pop(dname)
                continue

            if dreqs_set & set(result) == dreqs_set:
                # All dependencies were already added to the list
                # we can now insert this node
                result.append(dname)
                deptree.pop(dname)
                continue
    return result


def delete_duplicate_libs(wheeldirs: list[str], mangled: bool) -> None:
    """Given directories of unpacked wheels, preserve one copy of embedded libs.

    Deletes embedded libraries if they are provided by multiple wheels,
    only the first encountered lib is preserved.

    mangled=True tries to make this work for mangled lib names.
    This takes for granted that libraries have been mangled with
    libname-HASH.ext, which is what auditwheel and dwelvewheel
    currently do.

    Right now delocate on OSX doesn't apply any marshaling to file names,
    and thus this works correctly. Auditwheel currently seems to work
    because it retains the same marshaling hash across libraries,
    but usage of ``--exclude`` should be preferred over deduping the libs.
    """
    already_seen = set()

    for wheeldir in wheeldirs:
        print("Processing", wheeldir)
        for lib in itertools.chain(
            pathlib.Path(wheeldir).rglob(".dylibs/*"),
            pathlib.Path(wheeldir).rglob("*.libs/*.so"),
            pathlib.Path(wheeldir).rglob("*.dll"),
        ):
            if mangled:
                try:
                    libname = lib.name.split("-", 1)[0]
                except:
                    # seems it's not mangled
                    libname = lib.name
            else:
                libname = lib.name
            if libname in already_seen:
                print(f"Removing {lib.name} in {wheeldir} as already provided by another wheel.")
                lib.unlink()

                # On Windows we also have to remove the entry from load-order
                # generated by delvewheel
                for load_order in pathlib.Path(lib.parent).rglob(".load-order-*"):
                    with load_order.open() as load_order_f:
                        embedded_libs = load_order_f.readlines()
                    with load_order.open("w") as load_order_f:
                        for embedded_lib in embedded_libs:
                            if embedded_lib.strip() != lib.name:
                                load_order_f.write(embedded_lib)
            already_seen.add(libname)
