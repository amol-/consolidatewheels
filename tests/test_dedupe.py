from __future__ import annotations

import os
import pathlib

from consolidatewheels import dedupe, wheelsfunc

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
    ),
}


def test_dedupe(tmpdir):
    # Integration test that actually does the dedupe workflow.
    results = dedupe.dedupe(
        [FIXTURE_FILES["libfirst.whl"], FIXTURE_FILES["libtwo.whl"]], destdir=tmpdir
    )
    assert len(results) == 2

    os.makedirs(os.path.join(tmpdir, "wheeldirs"))
    wheeldirs = wheelsfunc.unpackwheels(
        results, workdir=os.path.join(tmpdir, "wheeldirs")
    )
    for wheeldir in wheeldirs:
        dylibs = []
        for p in pathlib.Path(wheeldir).rglob("*.so"):
            if "dylibs" in str(p):
                dylibs.append(p.name)

        # libfoo must have been removed from libtwo
        # and only preserved in libone
        if "libfirst-0.0.0" in wheeldir:
            assert dylibs == ["libfoo.so"]
        elif "libtwo-0.0.0" in wheeldir:
            assert dylibs == ["libbar.so"]
        else:
            assert False, f"unexpected wheel {wheeldir}"


def test_build_dependencies_tree():
    name2files, deptree = dedupe.build_dependencies_tree(
        [FIXTURE_FILES["libfirst.whl"], FIXTURE_FILES["libtwo.whl"]]
    )
    assert deptree == {"libfirst": [], "libtwo": ["libfirst"]}


def test_sort_dependencies():
    result = dedupe.sort_dependencies(
        {
            "libtwo2": ["libfirst"],
            "libthird": ["libtwo", "libfirst"],
            "libfourth": ["libthird"],
            "libtwo": ["libfirst"],
            "libfirst": [],
            "libother": ["numpy"],
        }
    )
    assert result == [
        "libfirst",
        "libother",
        "libtwo2",
        "libtwo",
        "libthird",
        "libfourth",
    ]
