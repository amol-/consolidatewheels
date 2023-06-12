from __future__ import annotations

import glob
import os

import pytest

from consolidatewheels import wheelsfunc

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
        wheelsfunc.unpackwheels(["notexisting.whl"], workdir=tmpdir)
    assert str(err.value) == "Unable to unpack notexisting.whl"

    # Test main workflow, should unpack the example wheel into tmpdir
    results = wheelsfunc.unpackwheels([FIXTURE_FILES["libtwo.whl"]], workdir=tmpdir)
    assert results == [os.path.join(tmpdir, "libtwo-0.0.0")]

    # Test that we catch when tmpdir is not empty
    with pytest.raises(ValueError) as err:
        wheelsfunc.unpackwheels(["notexisting.whl"], workdir=tmpdir)
    assert str(err.value) == "workdir must be empty"


def test_packwheels(tmpdir):
    wheeldir = wheelsfunc.unpackwheels([FIXTURE_FILES["libtwo.whl"]], workdir=tmpdir)
    wheeldir = wheeldir[0]

    # Ensure that packing a wheel directory works
    destdir = os.path.join(tmpdir, "wheels")
    wheelsfunc.packwheels([wheeldir], destdir=destdir)
    generated_wheel = glob.glob(os.path.join(destdir, "libtwo-0.0.0-cp310-cp310-*.whl"))
    assert generated_wheel

    # Ensure we trap errors
    with pytest.raises(RuntimeError) as err:
        wheelsfunc.packwheels(["non-existing-dir"], destdir=destdir)
    assert (
        str(err.value)
        == f"Unable to pack non-existing-dir into {os.path.join(destdir, 'tmp')}"
    )

    # Ensure that replacing an existing wheel works.
    existing_wheel = generated_wheel[0]
    assert os.path.exists(existing_wheel)
    result = wheelsfunc.packwheels([wheeldir], destdir=destdir)
    assert result and result[0] == existing_wheel
