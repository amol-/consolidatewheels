from __future__ import annotations

import os
import shutil
import subprocess


def unpackwheels(wheels: list[str], workdir: str) -> list[str]:
    """Unpack multiple wheels into workdir and returns list of resulting directories.

    All provided paths are expected to be in absolute format
    and the returned results are absolute paths too.
    """
    if os.listdir(workdir):
        raise ValueError("workdir must be empty")

    resulting_wheeldirs = []
    tmpdir = os.path.join(workdir, "tmp")
    for wheel in wheels:
        if subprocess.call(["wheel", "unpack", wheel, "--dest", tmpdir]):
            raise RuntimeError(f"Unable to unpack {wheel}")

        # This is a bit of an hack to preserve order of directories
        wheeldir = os.listdir(tmpdir)[0]
        shutil.move(os.path.join(tmpdir, wheeldir), workdir)
        resulting_wheeldirs.append(os.path.join(workdir, wheeldir))

    return resulting_wheeldirs


def packwheels(wheeldirs: list[str], destdir: str) -> list[str]:
    """Pack multiple wheel directories as wheel files into a destination path.

    If the destination path doesn't exist it will be created.
    """
    tmpdir = os.path.join(destdir, "tmp")
    os.makedirs(tmpdir, exist_ok=True)

    resulting_wheels = []
    for wheeldir in wheeldirs:
        if subprocess.call(["wheel", "pack", wheeldir, "--dest-dir", tmpdir]):
            raise RuntimeError(f"Unable to pack {wheeldir} into {tmpdir}")

        # This is a bit of an hack to preserve order of directories
        wheel = os.listdir(tmpdir)[0]
        expected_dest_file = os.path.join(destdir, wheel)
        if os.path.exists(expected_dest_file):
            os.unlink(expected_dest_file)
        shutil.move(os.path.join(tmpdir, wheel), destdir)
        resulting_wheels.append(os.path.join(destdir, wheel))
    return resulting_wheels
