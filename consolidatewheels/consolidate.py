from __future__ import annotations

import os
import pathlib
import subprocess
import tempfile


def consolidate(wheels: list[str], destdir: str) -> None:
    """Consolidate shared objects references within multiple wheels.

    Given a list of wheels, makes sure that they all share the
    same marshaling of libraries names when those libraries aren't
    already included in the wheel itself.

    The resulting new wheels are written into ``destdir``.

    Note: This function works in a temporary directory, so the
          current path for all functions invoked by it will
          be the the temporary directory.
    """
    wheels = [os.path.abspath(w) for w in wheels]
    with tempfile.TemporaryDirectory() as tmpcd:
        print(f"Working inside {tmpcd}")
        wheeldirs = unpackwheels(wheels, workdir=tmpcd)
        mangling_map = buildlibmap(wheeldirs)
        print(f"Applying consistent mangling: {mangling_map}")
        patch_wheeldirs(wheeldirs, mangling_map)
        packwheels(wheeldirs, destdir)


def patch_wheeldirs(wheeldirs, mangling_map):
    for wheeldir in wheeldirs:
        for lib_to_patch in pathlib.Path(wheeldir).rglob("*.so"):
            print(f"Patching {lib_to_patch}")
            for lib_to_mangle, lib_mangled_name in mangling_map.items():
                print(f"  {lib_to_mangle} -> {lib_mangled_name}")
                if subprocess.call(
                    [
                        "patchelf",
                        "--replace-needed",
                        lib_to_mangle,
                        lib_mangled_name,
                        lib_to_patch,
                    ]
                ):
                    raise RuntimeError(
                        f"Unable to apply mangling to {lib_to_patch}, "
                        "{lib_to_mangle}->{lib_mangled_name}"
                    )


def buildlibmap(wheeldirs):
    all_shared_objects = {}
    for wheeldir in wheeldirs:
        for lib in pathlib.Path(wheeldir).rglob("*.libs/*.so"):
            lib = os.path.basename(lib)
            libname, extension = os.path.splitext(lib)
            demangled_libname = libname.rsplit("-", 1)[0]
            demangled_lib = f"{demangled_libname}{extension}"
            all_shared_objects[demangled_lib] = lib
    return all_shared_objects


def unpackwheels(wheels: list[str], workdir: str) -> list[str]:
    """Unpack multiple wheels into workdir and returns list of resulting directories.

    All provided paths are expected to be in absolute format
    and the returned results are absolute paths too.
    """
    if os.listdir(workdir):
        raise ValueError("workdir must be empty")

    for wheel in wheels:
        if subprocess.call(["wheel", "unpack", wheel, "--dest", workdir]):
            raise RuntimeError(f"Unable to unpack {wheel}")
    return [os.path.join(workdir, wheel) for wheel in os.listdir(workdir)]


def packwheels(wheeldirs, destdir):
    os.makedirs(destdir, exist_ok=True)
    for wheeldir in wheeldirs:
        if subprocess.call(["wheel", "pack", wheeldir, "--dest-dir", destdir]):
            raise RuntimeError(f"Unable to pack {wheeldir} into {destdir}")
