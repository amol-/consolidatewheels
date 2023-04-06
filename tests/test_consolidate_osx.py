from __future__ import annotations

import os
import pathlib
from unittest import mock

from consolidatewheels import consolidate_osx, wheelsfunc

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


def test_consolidate(tmpdir):
    # Integration test that actually does the whole workflow.
    consolidated_id = "ASDFGH"
    with mock.patch("secrets.token_hex", return_value=consolidated_id), mock.patch(
        "consolidatewheels.consolidate_osx.update_library_id", return_value=0
    ) as mock_update_library_id, mock.patch(
        "consolidatewheels.consolidate_osx.update_dependency_path", return_value=0
    ) as mock_update_dependency_path, mock.patch(
        "consolidatewheels.consolidate_osx.resign_library"
    ) as mock_resign_library, mock.patch(
        "consolidatewheels.consolidate_osx.get_library_dependencies",
        return_value={"libfoo.so": "/fake/dependency/path/libfoo.so"},
    ):
        consolidate_osx.consolidate(
            [FIXTURE_FILES["libfirst.whl"], FIXTURE_FILES["libtwo.whl"]], destdir=tmpdir
        )

    # Find the workdir directly from the patchelf invokation
    workdir = str(mock_resign_library.call_args[0][-1]).split("libtwo-0.0.0")[0]

    mock_update_library_id.assert_has_calls(
        [
            mock.call(
                pathlib.Path(
                    os.path.join(workdir, "libfirst-0.0.0", ".dylibs", "libfoo.so")
                ),
                os.path.join("/CLD", consolidated_id, "libfoo.so"),
            )
        ],
        any_order=True,
    )

    mock_update_dependency_path.assert_has_calls(
        [
            mock.call(
                pathlib.Path(
                    os.path.join(workdir, "libtwo-0.0.0", ".dylibs", "libbar.so")
                ),
                "/fake/dependency/path/libfoo.so",
                os.path.join("/CLD", consolidated_id, "libfoo.so"),
            )
        ],
        any_order=True,
    )

    mock_resign_library.assert_has_calls(
        [
            mock.call(
                pathlib.Path(
                    os.path.join(workdir, "libtwo-0.0.0", ".dylibs", "libbar.so")
                )
            )
        ]
    )


def test_patch_wheeldirs(tmpdir):
    workdir = os.path.join(tmpdir, "wheeldirs")
    os.makedirs(workdir)
    wheeldirs = wheelsfunc.unpackwheels([FIXTURE_FILES["libtwo.whl"]], workdir=workdir)

    consolidate_id = "ASDFGH"
    with mock.patch("subprocess.call") as mock_subprocess_call:
        consolidate_osx.patch_wheeldirs(wheeldirs, consolidate_id)
    mock_subprocess_call.assert_has_calls(
        [
            mock.call(
                [
                    "install_name_tool",
                    pathlib.Path(
                        os.path.join(workdir, "libtwo-0.0.0", ".dylibs", "libfoo.so")
                    ),
                    "-id",
                    os.path.join("/CLD", consolidate_id, "libfoo.so"),
                ]
            ),
            mock.call(
                [
                    "codesign",
                    "--force",
                    "-s",
                    "-",
                    pathlib.Path(
                        os.path.join(workdir, "libtwo-0.0.0", ".dylibs", "libfoo.so")
                    ),
                ]
            ),
        ],
    )

    consolidate_id = "ASDFGH"
    with mock.patch(
        "consolidatewheels.consolidate_osx.get_library_dependencies",
        return_value={"libfoo.so": "/fake/dependency/path/libfoo.so"},
    ), mock.patch("subprocess.call") as mock_subprocess_call:
        consolidate_osx.patch_wheeldirs(wheeldirs * 2, consolidate_id)
    mock_subprocess_call.assert_has_calls(
        [
            mock.call(
                [
                    "install_name_tool",
                    pathlib.Path(
                        os.path.join(workdir, "libtwo-0.0.0", ".dylibs", "libfoo.so")
                    ),
                    "-change",
                    "/fake/dependency/path/libfoo.so",
                    os.path.join("/CLD", consolidate_id, "libfoo.so"),
                ]
            ),
        ]
    )


def test_get_library_dependencies():
    lpath = "@loader_path/../libfirst/.dylibs/libfoo.so"
    with mock.patch(
        "subprocess.run",
        return_value=mock.Mock(
            stdout=f"""
    libCat.dylib (compatibility version 0.0.0, current version 0.0.0)
    {lpath} (compatibility version 0.0.0, current version 0.0.0)
""".encode(
                "utf-8"
            )
        ),
    ):
        result = consolidate_osx.get_library_dependencies("FAKE_PATH")
    assert result == {"libfoo.so": lpath}
