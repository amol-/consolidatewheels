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
    # Integration test that actually does the dedupe workflow on OSX.
    results = dedupe.dedupe(
        [FIXTURE_FILES["libfirst.whl"], FIXTURE_FILES["libtwo.whl"]],
        destdir=tmpdir,
        mangled=False,
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


def test_dedupe_mangled(tmpdir):
    # Integration test that actually does the dedupe workflow on Windows.
    results = dedupe.dedupe(
        [FIXTURE_FILES["libfirst.whl"], FIXTURE_FILES["libtwo.whl"]],
        destdir=tmpdir,
        mangled=True,
    )
    assert len(results) == 2

    os.makedirs(os.path.join(tmpdir, "wheeldirs"))
    wheeldirs = wheelsfunc.unpackwheels(
        results, workdir=os.path.join(tmpdir, "wheeldirs")
    )
    for wheeldir in wheeldirs:
        dylibs = []
        for p in pathlib.Path(wheeldir).rglob("*.dll"):
            print(p)
            if ".libs" in str(p):
                dylibs.append(p.name)

        # libfoo must have been removed from libtwo
        # and only preserved in libone
        if "libfirst-0.0.0" in wheeldir:
            # foo should be mangled according to the libfirst mangling
            assert dylibs == ["foo-93c7258ead29c23ea6ef9c0778a28c9a.dll"]
        elif "libtwo-0.0.0" in wheeldir:
            # bar should be mangled according to libtwo mangling
            # and foo-1897da919eaed88c4c6f41b2487930e8.dll should have been deleted.
            assert dylibs == ["bar-d7b39fe6bdc290ef3cdc9fb9c8ded0b9.dll"]
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
