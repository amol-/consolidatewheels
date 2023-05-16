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

    Not that this takes for granted that all libraries were mangled by
    delvewheel and deduped by the dedupe step.
    """
    for wheeldir in wheeldirs:
        for lib_to_patch_path in pathlib.Path(wheeldir).rglob("*.dll"):
            lib_to_patch = str(lib_to_patch_path)
            print(f"Patching {lib_to_patch}")
            imports = _get_dll_imports(lib_to_patch)
            for lib_to_replace in imports:
                demangled_libname = demangle_libname(lib_to_replace)
                updated_libname = mangling_map.get(demangled_libname)
                if updated_libname is None:
                    # Library wasn't embedded into the wheel
                    continue
                print(f"  {lib_to_replace} -> {updated_libname}")
                if not _patch_dll(
                    lib_to_replace,
                    updated_libname,
                    lib_to_patch,
                ):
                    raise RuntimeError(
                        f"Unable to apply mangling to {lib_to_patch}, "
                        f"{lib_to_replace}->{updated_libname}"
                    )


def _get_dll_imports(lib_to_patch: str) -> list[str]:
    """Provide all DLLs used by a library"""
    imports = []
    with pefile.PE(lib_to_patch) as dlllib:
        for entry in dlllib.DIRECTORY_ENTRY_IMPORT:
            imports.append(entry.dll.decode("utf-8"))
    return imports


def _patch_dll(
    lib_to_replace: str, lib_replacement: str, lib_to_patch: str
) -> bool:
    """Patch lib_to_patch replacing the name of a dependency."""
    dlllib = pefile.PE(lib_to_patch)
    for entry in dlllib.DIRECTORY_ENTRY_IMPORT:
        if entry.dll.decode("utf-8") == lib_to_replace:
            if not dlllib.set_bytes_at_rva(
                entry.struct.Name, 
                lib_replacement.encode('ascii') + b'\0'
            ):
                return False
    dlllib.merge_modified_section_data()
    # Unclear how well PE behaves when closing it before writing it back
    # but if we don't close it, we get an error that the file is already in use.
    dlllib.close()
    dlllib.write(lib_to_patch)
    return True


def buildlibmap(wheeldirs: list[str]) -> dict[str, str]:
    """Compute how libraries embedded by delvewheel should be mangled.

    Across multiple wheel directories, find all the libraries that
    have been embedded by delvewheel and build a map of what mangling
    should be applied to each DLL.

    Report an error if the same directory has multiple possible mangling,
    this will usually signal that dedupe didn't run correctly when
    using consolidatewheels.
    """
    seen_shared_objects = {}  # type: dict[str, str]
    all_shared_objects = {}  # type: dict[str, str]
    for wheeldir in wheeldirs:
        for libpath in pathlib.Path(wheeldir).rglob("*.libs/*.dll"):
            demangled_lib = demangle_libname(libpath.name)
            if demangled_lib in all_shared_objects:
                seen_shared_object = seen_shared_objects[demangled_lib]
                raise ValueError(
                    f"Library {demangled_lib} appears multiple times: "
                    f"{seen_shared_object}, {libpath}. "
                    "Did dedupe step run?"
                )
            all_shared_objects[demangled_lib] = libpath.name
            seen_shared_objects[demangled_lib] = str(libpath)
    return all_shared_objects


def demangle_libname(libfilename):
    mangled_libname, extension = os.path.splitext(libfilename)
    demangled_libname = mangled_libname.rsplit("-", 1)[0]
    return f"{demangled_libname}{extension}"