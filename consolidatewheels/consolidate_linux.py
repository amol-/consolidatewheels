from __future__ import annotations

import os
import pathlib
import subprocess
import tempfile
import shutil

from .wheels import unpackwheels, packwheels


def consolidate(wheels: list[str], destdir: str) -> None:
    """Consolidate shared objects references within multiple wheels.

    Given a list of wheels, makes sure that they all share the
    same marshaling of libraries names when those libraries aren't
    already included in the wheel itself.

    The resulting new wheels are written into ``destdir``.
    """
    wheels = [os.path.abspath(w) for w in wheels]
    with tempfile.TemporaryDirectory() as tmpcd:
        print(f"Working inside {tmpcd}")
        wheeldirs = unpackwheels(wheels, workdir=tmpcd)
        mangling_map = buildlibmap(wheeldirs)
        print(f"Applying consistent mangling: {mangling_map}")
        patch_wheeldirs(wheeldirs, mangling_map)
        packwheels(wheeldirs, destdir)


def patch_wheeldirs(wheeldirs: list[str], mangling_map: dict[str, str]):
    """Provided a mapping of mangled library names, apply the manglign to all wheels.

    This traverses the content of all provided wheel directories
    looking for .so files. For every file, will patch the file dependencies
    so that they look for the mangled version of the library instead of
    the unmangled one.

    This will do nothing on files that already use the mangled version,
    or that don't depend on the library. For that, we rely on patchelf
    ignoring missing entries as we just invoke patchelf on everything.
    """
    for wheeldir in wheeldirs:
        for lib_to_patch_path in pathlib.Path(wheeldir).rglob("*.so"):
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
    """
    all_shared_objects = {}  # type: dict[str, str]
    for wheeldir in wheeldirs:
        for libpath in pathlib.Path(wheeldir).rglob("*.libs/*.so"):
            lib = libpath.name
            libname, extension = os.path.splitext(lib)
            demangled_libname = libname.rsplit("-", 1)[0]
            demangled_lib = f"{demangled_libname}{extension}"
            if demangled_lib in all_shared_objects:
                existing_mangling = all_shared_objects[demangled_lib]
                raise ValueError(
                    f"Library {demangled_lib} appears multiple times: "
                    f"{existing_mangling}, {lib}"
                )
            all_shared_objects[demangled_lib] = lib
    return all_shared_objects
