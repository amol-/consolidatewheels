from __future__ import annotations

import argparse
import os
import sys
from distutils.spawn import find_executable
from subprocess import CalledProcessError, check_output

from .consolidatewheels import consolidate


def main() -> int:
    """Main entry point of the command line tool.

    Executes consolidatewheels and returns the exit code.
    """
    if not verify_requirements():
        return 1

    opts = parse_options()
    consolidate(opts.wheels, opts.dest)
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
        "dest",
        default=None,
        nargs="?",
        help="Destination dir where to place consolidated wheels.",
    )
    opts = parser.parse_args()

    if opts.dest is None:
        # If no destination directory was provided,
        # by default save the new wheels in current directory.
        opts.dest = os.getcwd()

    return opts


def verify_requirements() -> bool:
    """Verifies that all system requirements are satisfied.

    Those can't be esily verified during install process,
    so it's easier to just check them when the tool starts.

    Returns ``False`` is the requirements are not satisfied.
    """
    if sys.platform != "linux":
        print("Error: This tool only supports Linux")
        return False

    # Ensure that patchelf exists and we can use it.
    if not find_executable("patchelf"):
        print("Cannot find required utility `patchelf` in PATH")
        return False

    try:
        check_output(["patchelf", "--version"]).decode("utf-8")
    except CalledProcessError:
        print("Could not call `patchelf` binary")
        return False

    # All requirements are in place, that's good!
    return True
