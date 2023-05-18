from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import tempfile

from . import consolidate_linux, consolidate_osx, consolidate_win, dedupe


def main() -> int:
    """Main entry point of the command line tool.

    Executes consolidatewheels and returns the exit code.
    """
    detected_system = platform.system().lower()

    if not requirements_satisfied():
        return 1

    opts = parse_options()
    if detected_system == "linux":
        consolidate_linux.consolidate(opts.wheels, opts.dest)
    elif detected_system == "windows":
        # On Windows, we need to include all libraries
        # so that they get mangled and reserve the right
        # size in the IMPORTS section of the DLL to account for
        # the mangling hash. That way we can then replace the hash
        # without risk of overflowing.
        # dedupe will take care that they don't appear twice.
        with tempfile.TemporaryDirectory() as dedupedir:
            wheels = dedupe.dedupe(opts.wheels, dedupedir, mangled=True)
            consolidate_win.consolidate(wheels, opts.dest)
    elif detected_system == "darwin":
        # On Mac, delocate does not mangle library names,
        # but there is no --exclude option,
        # so we just have to remove the extra lib.
        with tempfile.TemporaryDirectory() as dedupedir:
            wheels = dedupe.dedupe(opts.wheels, dedupedir)
            consolidate_osx.consolidate(wheels, opts.dest)
    return 0


def parse_options() -> argparse.Namespace:
    """Parse the options supported by the tool

    Returns an object with options as attributes.
    """
    parser = argparse.ArgumentParser(
        description="Export the report from the Engineering Report Clickup List"
    )
    parser.add_argument(
        "wheels", nargs="+", help="List of wheel files that have to be consolidated."
    )
    parser.add_argument(
        "--dest",
        default=None,
        nargs="?",
        help="Destination dir where to place consolidated wheels.",
    )
    opts = parser.parse_args()

    if opts.dest is None:
        # If no destination directory was provided,
        # by default save the new wheels in current directory.
        opts.dest = os.getcwd()

    # Ensure we always provide absolute path,
    # the rest of the script don't have to care about relative paths
    # when it changes working directory.
    opts.dest = os.path.abspath(opts.dest)
    return opts


def requirements_satisfied() -> bool:
    """Verifies that all system requirements are satisfied.

    Those can't be esily verified during install process,
    so it's easier to just check them when the tool starts.

    Returns ``False`` is the requirements are not satisfied.
    """
    detected_system = platform.system().lower()

    if detected_system == "darwin":
        if not shutil.which("install_name_tool"):
            print("Cannot find required utility `install_name_tool` in PATH")
            return False

        if not shutil.which("codesign"):
            print("Cannot find required utility `codesign` in PATH")
            return False
    elif detected_system == "linux":
        # Ensure that patchelf exists and we can use it.
        if not shutil.which("patchelf"):
            print("Cannot find required utility `patchelf` in PATH")
            return False

        try:
            subprocess.check_output(["patchelf", "--version"]).decode("utf-8")
        except subprocess.CalledProcessError:
            print("Could not call `patchelf` binary")
            return False
    elif detected_system == "windows":
        # At the moment there are no system dependencies required.
        pass
    else:
        print("Error: This tool only supports Linux, MacOSX and Windows")
        print("Detected System:", detected_system)
        return False

    # All requirements are in place, that's good!
    return True
