from __future__ import annotations

import os

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
