from __future__ import annotations

import os
import pathlib
import subprocess
import tempfile
from .wheelsfunc import packwheels, unpackwheels
import pefile


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
    looking for .so files. For every file, will patch the file dependencies
    so that they look for the mangled version of the library instead of
    the unmangled one.

    This will do nothing on files that already use the mangled version,
    or that don't depend on the library. For that, we rely on patchelf
    ignoring missing entries as we just invoke patchelf on everything.
    """
    for wheeldir in wheeldirs:
        for lib_to_patch_path in pathlib.Path(wheeldir).rglob("*.dll"):
            lib_to_patch = str(lib_to_patch_path)
            print(f"Patching {lib_to_patch}")
            for lib_to_mangle, lib_mangled_name in mangling_map.items():
                print(f"  {lib_to_mangle} -> {lib_mangled_name}")
                if not _patch_dll(
                    lib_to_mangle,
                    lib_mangled_name,
                    lib_to_patch,
                ):
                    raise RuntimeError(
                        f"Unable to apply mangling to {lib_to_patch}, "
                        f"{lib_to_mangle}->{lib_mangled_name}"
                    )



def _patch_dll(
    lib_to_mangle: str, lib_mangled_name: str, lib_to_patch: str
) -> bool:
    """Patch lib_to_patch replacing the name of a dependency."""
    dlllib = pefile.PE(lib_to_patch)
    for entry in dlllib.DIRECTORY_ENTRY_IMPORT:
        if entry.dll.decode("utf-8") == lib_to_mangle:
            if not dlllib.set_bytes_at_rva(
                entry.struct.Name, 
                lib_mangled_name.encode('ascii') + b'\0'
            ):
                return False
    dlllib.merge_modified_section_data()
    dlllib.write(lib_to_patch)
    return True


def buildlibmap(wheeldirs: list[str]) -> dict[str, str]:
    """Compute how libraries embedded by auditwheel should be mangled.

    Across multiple wheel directories, find all the libraries that
    have been embedded by auditwheel, and for those that are not mangled
    build a mapping of how they should be mangled.

    Report an error if the same directory has multiple possible mangling,
    this will usually signal that --exclude was forgotten for one or
    more libraries when invoking auditwheel.
    """
    seen_shared_objects = {}  # type: dict[str, str]
    all_shared_objects = {}  # type: dict[str, str]
    for wheeldir in wheeldirs:
        for libpath in pathlib.Path(wheeldir).rglob("*.dll"):
            demangled_lib = demangle_libname(libpath.name)
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


def demangle_libname(libfilename):
    mangled_libname, extension = os.path.splitext(libfilename)
    demangled_libname = mangled_libname.rsplit("-", 1)[0]
    return f"{demangled_libname}{extension}"