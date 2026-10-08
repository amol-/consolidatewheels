from __future__ import annotations

import os
import re
import shutil
from unittest import mock

import pytest

from consolidatewheels import consolidate_linux, wheelsfunc

HERE = os.path.dirname(__file__)
FIXTURE_FILES = {
    "libtwo.whl": os.path.join(
        HERE,
        "files",
        "libtwo-0.0.0-cp310-cp310-manylinux1_x86_64.manylinux_2_5_x86_64.whl",
    )
}


def test_buildlibmap(tmpdir):
    wheeldir = wheelsfunc.unpackwheels([FIXTURE_FILES["libtwo.whl"]], workdir=tmpdir)
    wheeldir = wheeldir[0]

    # Ensure that mapping works in common case
    mapping = consolidate_linux.buildlibmap([wheeldir])
    assert mapping == {
        "libbar.so": "libbar-3fac4b7b.so",
        "libfoo.so": "libfoo-3faccd3s.so",
    }

    # Ensure buildlibmap detects conflicts
    duplicatewheeldir = os.path.join(tmpdir, "anotherwheel")
    shutil.copytree(wheeldir, duplicatewheeldir)
    with pytest.raises(ValueError) as err:
        consolidate_linux.buildlibmap([wheeldir, duplicatewheeldir])
    assert re.search(r"Library lib.+\.so appears multiple times: ", str(err.value))


def test_buildlibmap_versioned_library(tmpdir):
    wheeldir = tmpdir.mkdir("wheel")
    libsdir = wheeldir.mkdir("package.libs")
    libsdir.join("libfoo-3fac4b7b.so.1.2.3").write("")

    mapping = consolidate_linux.buildlibmap([str(wheeldir)])

    assert mapping == {"libfoo.so.1.2.3": "libfoo-3fac4b7b.so.1.2.3"}


def test_buildlibmap_distinct_versions(tmp_path):
    libsdir = tmp_path / "package.libs"
    libsdir.mkdir()
    for name in ("libfoo-aaaaaaaa.so.0.12", "libfoo-bbbbbbbb.so.0.13"):
        (libsdir / name).touch()

    assert consolidate_linux.buildlibmap([str(tmp_path)]) == {
        "libfoo.so.0.12": "libfoo-aaaaaaaa.so.0.12",
        "libfoo.so.0.13": "libfoo-bbbbbbbb.so.0.13",
    }


def test_buildlibmap_duplicate_version(tmp_path):
    libsdir = tmp_path / "package.libs"
    libsdir.mkdir()
    for name in ("libfoo-aaaaaaaa.so.1.2", "libfoo-bbbbbbbb.so.1.2"):
        (libsdir / name).touch()

    with pytest.raises(ValueError, match=r"Library libfoo\.so\.1\.2 appears"):
        consolidate_linux.buildlibmap([str(tmp_path)])


@pytest.mark.parametrize("libfilename", ["libfoo.so", "libfoo.so.1.2"])
def test_buildlibmap_duplicate_unmangled_across_wheels(tmp_path, libfilename):
    # Skipping unnecessary remapping must not hide duplicate providers.
    for wheel in ("wheela", "wheelb"):
        libsdir = tmp_path / wheel / "package.libs"
        libsdir.mkdir(parents=True)
        (libsdir / libfilename).touch()

    wheeldirs = [str(tmp_path / "wheela"), str(tmp_path / "wheelb")]
    with pytest.raises(
        ValueError,
        match=rf"Library {re.escape(libfilename)} appears multiple times:",
    ):
        consolidate_linux.buildlibmap(wheeldirs)


def test_buildlibmap_double_mangled_library(tmp_path):
    # auditwheel can graft a library that carries a hash already, so a wheel
    # legitimately holds both names. Demangling the second one yields the
    # first, which is a real file and the name consumers already depend on,
    # so it must not become a mangling key.
    libsdir = tmp_path / "package.libs"
    libsdir.mkdir()
    for name in (
        "libgfortran-040039e1.so.5.0.0",
        "libgfortran-040039e1-0352e75f.so.5.0.0",
    ):
        (libsdir / name).touch()

    assert consolidate_linux.buildlibmap([str(tmp_path)]) == {
        "libgfortran.so.5.0.0": "libgfortran-040039e1.so.5.0.0",
    }


def test_buildlibmap_double_mangled_across_wheels(tmp_path):
    # The two copies can also arrive in separate wheels, which is what
    # happens when a package is built against another wheel's grafted
    # library. The same mangling map is applied to every wheel, so the
    # embedded name has to be recognised across all of them.
    for wheel, name in (
        ("wheela", "libgfortran-040039e1.so.5.0.0"),
        ("wheelb", "libgfortran-040039e1-0352e75f.so.5.0.0"),
    ):
        libsdir = tmp_path / wheel / "package.libs"
        libsdir.mkdir(parents=True)
        (libsdir / name).touch()

    wheeldirs = [str(tmp_path / "wheela"), str(tmp_path / "wheelb")]
    assert consolidate_linux.buildlibmap(wheeldirs) == {
        "libgfortran.so.5.0.0": "libgfortran-040039e1.so.5.0.0",
    }


@pytest.mark.parametrize(
    ("libfilename", "expected"),
    [
        ("libfoo-3fac4b7b.so", "libfoo.so"),
        ("libfoo-3fac4b7b.so.1.2.3", "libfoo.so.1.2.3"),
        ("libfoo-deadbeef.solver.so.1", "libfoo.solver.so.1"),
        ("libfoo.so.1.2.3", "libfoo.so.1.2.3"),
        ("libopenblas-r0-3fac4b7b.3.29.so", "libopenblas-r0.3.29.so"),
    ],
)
def test_demangle_libname(libfilename, expected):
    assert consolidate_linux.demangle_libname(libfilename) == expected


def test_patch_wheeldirs(tmpdir):
    wheeldir = wheelsfunc.unpackwheels([FIXTURE_FILES["libtwo.whl"]], workdir=tmpdir)
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
        consolidate_linux.patch_wheeldirs(
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
            consolidate_linux.patch_wheeldirs(
                [wheeldir, duplicatewheeldir],
                mangling_map={"libbar.so": "libbar-3fac4b7b.so"},
            )
    assert re.compile(
        r"Unable to apply mangling to .+, libbar.so->libbar-3fac4b7b.so"
    ).match(str(err.value))


def test_patch_wheeldirs_versioned_library(tmpdir):
    wheeldir = tmpdir.mkdir("wheel")
    versioned_lib = wheeldir.join("libfoo.so.1.2.3")
    versioned_lib.write("")

    with mock.patch("subprocess.call", return_value=0) as mock_call:
        consolidate_linux.patch_wheeldirs(
            [str(wheeldir)],
            mangling_map={"libfoo.so.1.2.3": "libfoo-3fac4b7b.so.1.2.3"},
        )

    mock_call.assert_called_once_with(
        [
            "patchelf",
            "--replace-needed",
            "libfoo.so.1.2.3",
            "libfoo-3fac4b7b.so.1.2.3",
            str(versioned_lib),
        ]
    )


def test_consolidate(tmpdir):
    # Integration test that actually does the whole workflow.

    with mock.patch(
        "consolidatewheels.consolidate_linux._invoke_patchelf", return_value=0
    ) as mock_call:
        consolidate_linux.consolidate([FIXTURE_FILES["libtwo.whl"]], destdir=tmpdir)
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
