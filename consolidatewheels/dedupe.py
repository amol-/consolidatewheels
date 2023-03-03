import os
import re
import tempfile
import pathlib

import pkginfo
import pkg_resources

from . import consolidate


def dedupe(wheels: list[str], destdir: str) -> None:
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
        print(f"Working inside {tmpcd}")
        wheeldirs = consolidate.unpackwheels(wheels, workdir=tmpcd)
        delete_duplicate_libs(wheeldirs)
        consolidate.packwheels(wheeldirs, destdir)


def build_dependencies_tree(wheels: list[str]) -> tuple[dict[str, str], dict[str, list[str]]]:
    deptree = {}
    name2file = {}

    for wheel_fname in wheels:
        distribution_name, _ = os.path.basename(wheel_fname).split('-', 1)
        name2file[distribution_name] = wheel_fname
        deptree[distribution_name] = dependencies = []

        metadata = pkginfo.get_metadata(wheel_fname)
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


def delete_duplicate_libs(wheeldirs: list[str]) -> None:
    already_seen = set()

    for wheeldir in wheeldirs:
        print("Processing", wheeldir)
        for lib in pathlib.Path(wheeldir).rglob(".dylibs/*"):
            libname = lib.name
            if libname in already_seen:
                print(f"Removing {libname} as already provided by another wheel.")
                lib.unlink()
            already_seen.add(libname)