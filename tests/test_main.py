from __future__ import annotations

import argparse
import os
import platform
from subprocess import CalledProcessError
from unittest import mock

from consolidatewheels import __main__  # noqa
from consolidatewheels import main


def test_options():
    # No options provided ensure we error.
    with mock.patch("sys.argv", ["consolidatewheels"]), mock.patch(
        "sys.exit"
    ) as sys_exit:
        main.parse_options()
    sys_exit.assert_called_with(2)

    # Invalid options provided ensure we error.
    with mock.patch(
        "sys.argv", ["consolidatewheels", "--not-existing-option"]
    ), mock.patch("sys.exit") as sys_exit:
        main.parse_options()
    sys_exit.assert_called_with(2)

    # Ensure options work
    with mock.patch(
        "sys.argv",
        ["consolidatewheels", "wheel1", "wheel2", "--dest", "./outputdir"],
    ):
        opts = main.parse_options()
    assert opts.wheels == ["wheel1", "wheel2"]
    assert opts.dest == os.path.abspath("./outputdir")

    # Ensure we use current directory for output when none provided
    with mock.patch("sys.argv", ["consolidatewheels", "wheel1"]):
        opts = main.parse_options()
    assert opts.wheels == ["wheel1"]
    assert opts.dest == os.path.abspath(os.getcwd())


def test_requirements_satisfied():
    # Ensure we detect when it's not a supported platform
    with mock.patch("platform.system", return_value="os2"):
        verify_result = main.requirements_satisfied()
    assert verify_result is False

    # Ensure the check passes when dependencies are satisfied
    with mock.patch("shutil.which", return_value="fakepath"), mock.patch(
        "subprocess.check_output"
    ):
        verify_result = main.requirements_satisfied()
    assert verify_result is True

    # Ensure we detect lack of patchelf
    with mock.patch("platform.system", return_value="linux"), mock.patch(
        "shutil.which"
    ) as shutil_which:
        shutil_which.return_value = None
        verify_result = main.requirements_satisfied()
    assert verify_result is False

    # Ensure we detect patchelf not working.
    with mock.patch("platform.system", return_value="linux"), mock.patch(
        "shutil.which", return_value=["fakepath"]
    ), mock.patch(
        "subprocess.check_output",
        side_effect=CalledProcessError(returncode=1, cmd="patchelf"),
    ):
        verify_result = main.requirements_satisfied()
    assert verify_result is False

    # Ensure we detect missing install_name_tool.
    with mock.patch("platform.system", return_value="darwin"), mock.patch(
        "shutil.which", return_value=None
    ):
        verify_result = main.requirements_satisfied()
    assert verify_result is False

    # Ensure we detect missing codesign.
    with mock.patch("platform.system", return_value="darwin"), mock.patch(
        "shutil.which", side_effect=["fakepath", None]
    ):
        verify_result = main.requirements_satisfied()
    assert verify_result is False


def test_main():
    # Mostly just test that main runs consolidate at the end.
    default_options = argparse.Namespace()
    default_options.dest = "somedestdir"
    default_options.wheels = ["one", "two"]

    # Simulate Linux
    with mock.patch("platform.system", return_value="linux"), mock.patch(
        "consolidatewheels.main.requirements_satisfied", return_value=True
    ), mock.patch(
        "consolidatewheels.main.parse_options", return_value=default_options
    ), mock.patch(
        "consolidatewheels.consolidate_linux.consolidate"
    ) as consolidate_func:
        main.main()
    consolidate_func.assert_called_once_with(
        default_options.wheels, default_options.dest
    )

    # Simulate OSX
    with mock.patch("platform.system", return_value="darwin"), mock.patch(
        "consolidatewheels.main.requirements_satisfied", return_value=True
    ), mock.patch(
        "consolidatewheels.main.parse_options", return_value=default_options
    ), mock.patch(
        "consolidatewheels.dedupe.dedupe", return_value=default_options.wheels
    ), mock.patch(
        "consolidatewheels.consolidate_osx.consolidate"
    ) as consolidate_func:
        main.main()
    consolidate_func.assert_called_once_with(
        default_options.wheels, default_options.dest
    )

    # Ensure we exit if we fail checking requirements
    with mock.patch(
        "consolidatewheels.main.requirements_satisfied", return_value=False
    ), mock.patch(
        "consolidatewheels.consolidate_linux.consolidate"
    ) as consolidate_linux_func, mock.patch(
        "consolidatewheels.consolidate_osx.consolidate"
    ) as consolidate_osx_func:
        return_value = main.main()
    assert return_value == 1

    consolidate_func = {
        "linux": consolidate_linux_func,
        "darwin": consolidate_osx_func,
    }[platform.system().lower()]
    consolidate_func.assert_not_called()
