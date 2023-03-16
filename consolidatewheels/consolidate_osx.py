from __future__ import annotations

import os
import pathlib
import secrets
import subprocess
import tempfile

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
        consolidated_id = secrets.token_hex(16)
        print(f"Applying consistent references: {consolidated_id}")
        patch_wheeldirs(wheeldirs, consolidated_id)
        packwheels(wheeldirs, destdir)


def patch_wheeldirs(wheeldirs, consolidated_id):
    patched_identifier = {}
    seen_dependencies = set()
    for wheeldir in wheeldirs:
        for lib_to_patch_path in pathlib.Path(wheeldir).rglob(".dylibs/*"):
            libname = lib_to_patch_path.name
            if libname not in patched_identifier:
                # First time we encounter the library,
                # this means we only need to change the ID.
                # The path was already set by delocate.
                patched_identifier[libname] = libid = os.path.join(
                    "/CLD", f"{consolidated_id}", libname
                )
                update_library_id(lib_to_patch_path, libid)
                resign_library(lib_to_patch_path)

        seen_in_wheel = set()
        for lib_to_patch_path in pathlib.Path(wheeldir).rglob("*.so"):
            dependencies = get_library_dependencies(lib_to_patch_path)
            for dependency, dependency_path in dependencies.items():
                seen_in_wheel.add(dependency)
                if dependency not in seen_dependencies:
                    # This library is seen for the first time,
                    # so we don't want to patch it, so it can load from its path.
                    continue
                update_dependency_path(
                    lib_to_patch_path, dependency_path, patched_identifier[dependency]
                )
            resign_library(lib_to_patch_path)
        seen_dependencies |= seen_in_wheel


def update_library_id(libpath, libid):
    return subprocess.call(["install_name_tool", libpath, "-id", libid])


def update_dependency_path(libpath, deppath, newdeppath):
    return subprocess.call(
        ["install_name_tool", libpath, "-change", deppath, newdeppath]
    )


def resign_library(libpath):
    return subprocess.call(["codesign", "--force", "-s", "-", libpath])


def get_library_dependencies(libpath):
    out = subprocess.run(["otool", "-X", "-L", libpath], capture_output=True)
    libpaths = {}
    for line in out.stdout.decode("utf-8").splitlines():
        dependency, _ = line.strip().split(maxsplit=1)
        if not dependency.startswith("@loader_path"):
            # Libs included by delocate will all be relative to the loader
            continue
        libname = os.path.basename(dependency)
        libpaths[libname] = dependency
    return libpaths
