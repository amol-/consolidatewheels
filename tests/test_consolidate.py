from __future__ import annotations

import glob
import os
import re
import shutil
from unittest import mock

import pytest

from consolidatewheels import consolidate

HERE = os.path.dirname(__file__)
FIXTURE_FILES = {
    "libtwo.whl": os.path.join(
        HERE,
        "files",
        "libtwo-0.0.0-cp310-cp310-manylinux1_x86_64.manylinux_2_5_x86_64.whl",
    )
}


def test_unpackwheels(tmpdir):
    # Test catching invalid wheels
    with pytest.raises(RuntimeError) as err:
        consolidate.unpackwheels(["notexisting.whl"], workdir=tmpdir)
    assert str(err.value) == "Unable to unpack notexisting.whl"

    # Test main workflow, should unpack the example wheel into tmpdir
    results = consolidate.unpackwheels([FIXTURE_FILES["libtwo.whl"]], workdir=tmpdir)
    assert results == [os.path.join(tmpdir, "libtwo-0.0.0")]

    # Test that we catch when tmpdir is not empty
    with pytest.raises(ValueError) as err:
        consolidate.unpackwheels(["notexisting.whl"], workdir=tmpdir)
    assert str(err.value) == "workdir must be empty"


def test_packwheels(tmpdir):
    wheeldir = consolidate.unpackwheels([FIXTURE_FILES["libtwo.whl"]], workdir=tmpdir)
    wheeldir = wheeldir[0]

    # Ensure that packing a wheel directory works
    destdir = os.path.join(tmpdir, "wheels")
    consolidate.packwheels([wheeldir], destdir=destdir)
    assert glob.glob(os.path.join(destdir, "libtwo-0.0.0-cp310-cp310-*.whl"))

    # Ensure we trap errors
    with pytest.raises(RuntimeError) as err:
        consolidate.packwheels(["non-existing-dir"], destdir=destdir)
    assert str(err.value) == f"Unable to pack non-existing-dir into {destdir}"


def test_buildlibmap(tmpdir):
    wheeldir = consolidate.unpackwheels([FIXTURE_FILES["libtwo.whl"]], workdir=tmpdir)
    wheeldir = wheeldir[0]

    # Ensure that mapping works in common case
    mapping = consolidate.buildlibmap([wheeldir])
    assert mapping == {"libbar.so": "libbar-3fac4b7b.so"}

    # Ensure buildlibmap detects conflicts
    duplicatewheeldir = os.path.join(tmpdir, "anotherwheel")
    shutil.copytree(wheeldir, duplicatewheeldir)
    with pytest.raises(ValueError) as err:
        consolidate.buildlibmap([wheeldir, duplicatewheeldir])
    assert (
        str(err.value) == "Library libbar.so appears multiple times: "
        "libbar-3fac4b7b.so, libbar-3fac4b7b.so"
    )


def test_patch_wheeldirs(tmpdir):
    wheeldir = consolidate.unpackwheels([FIXTURE_FILES["libtwo.whl"]], workdir=tmpdir)
    wheeldir = wheeldir[0]

    # Create a second wheel without the mangled lib
    duplicatewheeldir = os.path.join(tmpdir, "anotherwheel")
    shutil.copytree(wheeldir, duplicatewheeldir)
    os.rename(
        os.path.join(duplicatewheeldir, "libtwo.libs", "libbar-3fac4b7b.so"),
        os.path.join(duplicatewheeldir, "libtwo.libs", "libotherlib.so"),
    )

    # Ensure that patch_wheels patches all shared objects in provided wheels
    # according to the mangling_map
    with mock.patch("subprocess.call", return_value=0) as mock_call:
        consolidate.patch_wheeldirs(
            [wheeldir, duplicatewheeldir],
            mangling_map={"libbar.so": "libbar-3fac4b7b.so"},
        )
    mock_call.assert_has_calls(
        [
            mock.call(
                [
                    "patchelf",
                    "--replace-needed",
                    "libbar.so",
                    "libbar-3fac4b7b.so",
                    os.path.join(duplicatewheeldir, "libtwo.libs", "libotherlib.so"),
                ]
            ),
            mock.call(
                [
                    "patchelf",
                    "--replace-needed",
                    "libbar.so",
                    "libbar-3fac4b7b.so",
                    os.path.join(
                        duplicatewheeldir,
                        "libtwo",
                        "_libtwo.cpython-310-x86_64-linux-gnu.so",
                    ),
                ]
            ),
            mock.call(
                [
                    "patchelf",
                    "--replace-needed",
                    "libbar.so",
                    "libbar-3fac4b7b.so",
                    os.path.join(
                        wheeldir, "libtwo", "_libtwo.cpython-310-x86_64-linux-gnu.so"
                    ),
                ]
            ),
        ],
        any_order=True,
    )

    # Ensure we trap errors in patching files
    with pytest.raises(RuntimeError) as err:
        with mock.patch("subprocess.call", return_value=1) as mock_call:
            consolidate.patch_wheeldirs(
                [wheeldir, duplicatewheeldir],
                mangling_map={"libbar.so": "libbar-3fac4b7b.so"},
            )
    assert re.compile(
        r"Unable to apply mangling to .+, libbar.so->libbar-3fac4b7b.so"
    ).match(str(err.value))


def test_consolidate(tmpdir):
    # Integration test that actually does the whole workflow.

    with mock.patch(
        "consolidatewheels.consolidate._invoke_patchelf", return_value=0
    ) as mock_call:
        consolidate.consolidate([FIXTURE_FILES["libtwo.whl"]], destdir=tmpdir)
    # Find the workdir directly from the patchelf invokation
    workdir = mock_call.call_args[0][-1].split("libtwo-0.0.0")[0]
    mock_call.assert_has_calls(
        [
            mock.call(
                "libbar.so",
                "libbar-3fac4b7b.so",
                os.path.join(
                    workdir, "libtwo-0.0.0", "libtwo.libs", "libbar-3fac4b7b.so"
                ),
            ),
            mock.call(
                "libbar.so",
                "libbar-3fac4b7b.so",
                os.path.join(
                    workdir,
                    "libtwo-0.0.0",
                    "libtwo",
                    "_libtwo.cpython-310-x86_64-linux-gnu.so",
                ),
            ),
        ],
        any_order=True,
    )
