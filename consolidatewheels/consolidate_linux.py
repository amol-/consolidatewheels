from __future__ import annotations

import itertools
import os
import pathlib
import subprocess
import tempfile
from typing import Iterator

from .wheelsfunc import packwheels, unpackwheels


def consolidate(wheels: list[str], destdir: str) -> None:
    """Consolidate shared objects references within multiple wheels.

    Given a list of wheels, makes sure that they all share the
    same marshaling of libraries names when those libraries aren't
    already included in the wheel itself.

    The resulting new wheels are written into ``destdir``.
    """
    wheels = [os.path.abspath(w) for w in wheels]
    with tempfile.TemporaryDirectory() as tmpcd:
        print(f"Consolidate, Working inside {tmpcd}")
        wheeldirs = unpackwheels(wheels, workdir=tmpcd)
        mangling_map = buildlibmap(wheeldirs)
        print(f"Applying consistent mangling: {mangling_map}")
        patch_wheeldirs(wheeldirs, mangling_map)
        packwheels(wheeldirs, destdir)


def patch_wheeldirs(wheeldirs: list[str], mangling_map: dict[str, str]):
    """Provided a mapping of mangled library names, apply the manglign to all wheels.

    This traverses the content of all provided wheel directories
    looking for shared object files. For every file, will patch the file dependencies
    so that they look for the mangled version of the library instead of
    the unmangled one.

    This will do nothing on files that already use the mangled version,
    or that don't depend on the library. For that, we rely on patchelf
    ignoring missing entries as we just invoke patchelf on everything.
    """
    for wheeldir in wheeldirs:
        for lib_to_patch_path in _find_shared_objects(wheeldir):
            lib_to_patch = str(lib_to_patch_path)
            print(f"Patching {lib_to_patch}")
            for lib_to_mangle, lib_mangled_name in mangling_map.items():
                print(f"  {lib_to_mangle} -> {lib_mangled_name}")
                if _invoke_patchelf(
                    lib_to_mangle,
                    lib_mangled_name,
                    lib_to_patch,
                ):
                    raise RuntimeError(
                        f"Unable to apply mangling to {lib_to_patch}, "
                        f"{lib_to_mangle}->{lib_mangled_name}"
                    )


def _invoke_patchelf(
    lib_to_mangle: str, lib_mangled_name: str, lib_to_patch: str
) -> int:
    """Just a simple wrapper to subprocess.call to ease testing."""
    return subprocess.call(
        [
            "patchelf",
            "--replace-needed",
            lib_to_mangle,
            lib_mangled_name,
            lib_to_patch,
        ]
    )


def buildlibmap(wheeldirs: list[str]) -> dict[str, str]:
    """Compute how libraries embedded by auditwheel should be mangled.

    Across multiple wheel directories, find all the libraries that
    have been embedded by auditwheel, and for those that are not mangled
    build a mapping of how they should be mangled.

    Report an error if the same directory has multiple possible mangling,
    this will usually signal that --exclude was forgotten for one or
    more libraries when invoking auditwheel.

    Versioned libraries are mapped under their exact versioned name, so
    libfoo.so.1.2.3 is not assumed to satisfy a dependency recorded as
    libfoo.so.1. Recovering the shorter soname would mean reading it
    from the library itself.

    A library auditwheel mangled twice, libfoo-aaaaaaaa-bbbbbbbb.so,
    demangles onto libfoo-aaaaaaaa.so, which is another embedded library
    and the name its users already depend on, so it is left alone. An
    unmangled namesake is a genuine duplicate and is still reported.
    """
    embedded_names = {
        libpath.name
        for wheeldir in wheeldirs
        for libpath in _find_shared_objects(wheeldir)
        if libpath.parent.name.endswith(".libs")
    }
    seen_shared_objects = {}  # type: dict[str, str]
    all_shared_objects = {}  # type: dict[str, str]
    for wheeldir in wheeldirs:
        for libpath in _find_shared_objects(wheeldir):
            if not libpath.parent.name.endswith(".libs"):
                continue
            demangled_lib = demangle_libname(libpath.name)
            if (
                demangled_lib in embedded_names
                and demangle_libname(demangled_lib) != demangled_lib
            ):
                continue
            if demangled_lib in all_shared_objects:
                seen_shared_object = seen_shared_objects[demangled_lib]
                raise ValueError(
                    f"Library {demangled_lib} appears multiple times: "
                    f"{seen_shared_object}, {libpath}. "
                    "Did you forget --exclude?"
                )
            all_shared_objects[demangled_lib] = libpath.name
            seen_shared_objects[demangled_lib] = str(libpath)
    return all_shared_objects


def _find_shared_objects(wheeldir: str) -> Iterator[pathlib.Path]:
    """Find unversioned and versioned shared libraries in an unpacked wheel."""
    return itertools.chain(
        pathlib.Path(wheeldir).rglob("*.so"),
        pathlib.Path(wheeldir).rglob("*.so.[0-9]*"),
    )


def demangle_libname(libfilename: str) -> str:
    """Remove auditwheel's hash from the basename before the first dot."""
    base, ext = libfilename.split(".", 1)
    return f"{base.rsplit('-', 1)[0]}.{ext}"
