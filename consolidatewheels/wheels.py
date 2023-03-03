import os
import subprocess
import shutil


def unpackwheels(wheels: list[str], workdir: str) -> list[str]:
    """Unpack multiple wheels into workdir and returns list of resulting directories.

    All provided paths are expected to be in absolute format
    and the returned results are absolute paths too.
    """
    if os.listdir(workdir):
        raise ValueError("workdir must be empty")

    wheeldirs = []
    tmpdir = os.path.join(workdir, "tmp")
    for wheel in wheels:
        if subprocess.call(["wheel", "unpack", wheel, "--dest", tmpdir]):
            raise RuntimeError(f"Unable to unpack {wheel}")

        # This is a bit of an hack to preserve order of directories
        wheeldir = os.listdir(tmpdir)[0]
        shutil.move(os.path.join(tmpdir, wheeldir), workdir)
        wheeldirs.append(os.path.join(workdir, wheeldir))

    return wheeldirs


def packwheels(wheeldirs: list[str], destdir: str) -> None:
    """Pack multiple wheel directories as wheel files into a destination path.

    If the destination path doesn't exist it will be created.
    """
    os.makedirs(destdir, exist_ok=True)
    for wheeldir in wheeldirs:
        if subprocess.call(["wheel", "pack", wheeldir, "--dest-dir", destdir]):
            raise RuntimeError(f"Unable to pack {wheeldir} into {destdir}")
