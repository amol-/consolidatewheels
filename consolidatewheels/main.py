from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys

from . import consolidatewheels


def main() -> int:
    """Main entry point of the command line tool.

    Executes consolidatewheels and returns the exit code.
    """
    if not requirements_satisfied():
        return 1

    opts = parse_options()
    consolidatewheels.consolidate(opts.wheels, opts.dest)
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
    if sys.platform != "linux":
        print("Error: This tool only supports Linux")
        return False

    # Ensure that patchelf exists and we can use it.
    if not shutil.which("patchelf"):
        print("Cannot find required utility `patchelf` in PATH")
        return False

    try:
        subprocess.check_output(["patchelf", "--version"]).decode("utf-8")
    except subprocess.CalledProcessError:
        print("Could not call `patchelf` binary")
        return False

    # All requirements are in place, that's good!
    return True
