from __future__ import annotations

import glob
import os
import re
import shutil
from unittest import mock

import pytest

from consolidatewheels import dedupe

HERE = os.path.dirname(__file__)
FIXTURE_FILES = {
    "libtwo.whl": os.path.join(
        HERE,
        "files",
        "libtwo-0.0.0-cp310-cp310-manylinux1_x86_64.manylinux_2_5_x86_64.whl",
    ),
    "libfirst.whl": os.path.join(
        HERE,
        "files",
        "libfirst-0.0.0-cp310-cp310-manylinux1_x86_64.manylinux_2_5_x86_64.whl",
    )
}


def test_dedupe(tmpdir):
    # Integration test that actually does the dedupe workflow.
    results = dedupe.dedupe(
        [FIXTURE_FILES["libtwo.whl"], FIXTURE_FILES["libfirst.whl"]], 
        destdir=tmpdir
    )


