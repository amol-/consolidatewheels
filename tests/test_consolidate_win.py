from __future__ import annotations

import os
import re
import shutil
from unittest import mock

import pytest

from consolidatewheels import consolidate_win, wheelsfunc

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
    mapping = consolidate_win.buildlibmap([wheeldir])
    assert mapping == {
        "bar.dll": "bar-d7b39fe6bdc290ef3cdc9fb9c8ded0b9.dll",
        "foo.dll": "foo-1897da919eaed88c4c6f41b2487930e8.dll",
    }

    # Ensure buildlibmap detects conflicts
    duplicatewheeldir = os.path.join(tmpdir, "anotherwheel")
    shutil.copytree(wheeldir, duplicatewheeldir)
    with pytest.raises(ValueError) as err:
        consolidate_win.buildlibmap([wheeldir, duplicatewheeldir])
    assert re.search(r"Library .+\.dll appears multiple times: ", str(err.value))


def test_patch_wheeldirs(tmpdir):
    wheeldir = wheelsfunc.unpackwheels([FIXTURE_FILES["libtwo.whl"]], workdir=tmpdir)
    wheeldir = wheeldir[0]

    # Create a second wheel without the mangled lib
    duplicatewheeldir = os.path.join(tmpdir, "anotherwheel")
    shutil.copytree(wheeldir, duplicatewheeldir)
    os.rename(
        os.path.join(
            duplicatewheeldir, "libtwo.libs", "bar-d7b39fe6bdc290ef3cdc9fb9c8ded0b9.dll"
        ),
        os.path.join(duplicatewheeldir, "libtwo.libs", "otherlib.dll"),
    )

    # Ensure that patch_wheels patches all shared objects in provided wheels
    # according to the mangling_map
    with mock.patch(
        "consolidatewheels.consolidate_win._get_dll_imports",
        return_value=["bar-d7b39fe6bdc290ef3cdc9fb9c8ded0b9.dll"],
    ), mock.patch(
        "consolidatewheels.consolidate_win._patch_dll", return_value=True
    ) as mock_call:
        consolidate_win.patch_wheeldirs(
            [wheeldir, duplicatewheeldir],
            mangling_map={"bar.dll": "bar-REPLACEMENTHASH.dll"},
        )
    mock_call.assert_has_calls(
        [
            mock.call(
                "bar-d7b39fe6bdc290ef3cdc9fb9c8ded0b9.dll",
                "bar-REPLACEMENTHASH.dll",
                os.path.join(
                    duplicatewheeldir,
                    "libtwo.libs",
                    "foo-1897da919eaed88c4c6f41b2487930e8.dll",
                ),
            ),
            mock.call(
                "bar-d7b39fe6bdc290ef3cdc9fb9c8ded0b9.dll",
                "bar-REPLACEMENTHASH.dll",
                os.path.join(duplicatewheeldir, "libtwo.libs", "otherlib.dll"),
            ),
            mock.call(
                "bar-d7b39fe6bdc290ef3cdc9fb9c8ded0b9.dll",
                "bar-REPLACEMENTHASH.dll",
                os.path.join(
                    wheeldir, "libtwo.libs", "bar-d7b39fe6bdc290ef3cdc9fb9c8ded0b9.dll"
                ),
            ),
            mock.call(
                "bar-d7b39fe6bdc290ef3cdc9fb9c8ded0b9.dll",
                "bar-REPLACEMENTHASH.dll",
                os.path.join(
                    wheeldir, "libtwo.libs", "foo-1897da919eaed88c4c6f41b2487930e8.dll"
                ),
            ),
        ],
        any_order=True,
    )

    # Ensure we trap errors in patching files
    with pytest.raises(RuntimeError) as err:
        with mock.patch(
            "consolidatewheels.consolidate_win._patch_dll", return_value=False
        ), mock.patch(
            "consolidatewheels.consolidate_win._get_dll_imports",
            return_value=["bar-3fac4b7b.dll"],
        ):
            consolidate_win.patch_wheeldirs(
                [wheeldir, duplicatewheeldir],
                mangling_map={"bar.dll": "bar-NEWHASH.dll"},
            )
    assert re.compile(
        r"Unable to apply mangling to .+, bar-3fac4b7b.dll->bar-NEWHASH.dll"
    ).match(str(err.value))


def test_consolidate(tmpdir):
    # Integration test that actually does the whole workflow.

    with mock.patch(
        "consolidatewheels.consolidate_win._patch_dll"
    ) as mock_call, mock.patch(
        "consolidatewheels.consolidate_win._get_dll_imports",
        return_value=["bar-mangled.dll", "missing-mangled.dll"],
    ):
        consolidate_win.consolidate([FIXTURE_FILES["libtwo.whl"]], destdir=tmpdir)
    # Find the workdir directly from the patchelf invokation
    workdir = mock_call.call_args[0][-1].split("libtwo-0.0.0")[0]
    mock_call.assert_has_calls(
        [
            mock.call(
                "bar-mangled.dll",
                "bar-d7b39fe6bdc290ef3cdc9fb9c8ded0b9.dll",
                os.path.join(
                    workdir,
                    "libtwo-0.0.0",
                    "libtwo.libs",
                    "bar-d7b39fe6bdc290ef3cdc9fb9c8ded0b9.dll",
                ),
            ),
            mock.call(
                "bar-mangled.dll",
                "bar-d7b39fe6bdc290ef3cdc9fb9c8ded0b9.dll",
                os.path.join(
                    workdir,
                    "libtwo-0.0.0",
                    "libtwo.libs",
                    "foo-1897da919eaed88c4c6f41b2487930e8.dll",
                ),
            ),
        ],
        any_order=True,
    )


def test_patch_dll_fail(tmpdir):
    # Integration test that actually does the whole workflow.

    with mock.patch(
        "consolidatewheels.consolidate_win._patch_dll", return_value=False
    ), mock.patch(
        "consolidatewheels.consolidate_win._get_dll_imports",
        return_value=["bar-mangled.dll"],
    ):
        with pytest.raises(RuntimeError) as err:
            consolidate_win.consolidate([FIXTURE_FILES["libtwo.whl"]], destdir=tmpdir)
        assert str(err.value).startswith("Unable to apply mangling to ")
        assert str(err.value).endswith(
            ", bar-mangled.dll->bar-d7b39fe6bdc290ef3cdc9fb9c8ded0b9.dll"
        )


def test_get_dll_imports():
    with mock.patch("pefile.PE") as mock_pe:
        mock_pe.return_value.__enter__.return_value = mock.Mock(
            DIRECTORY_ENTRY_IMPORT=[mock.Mock(dll=b"test-random.dll")]
        )
        imports = consolidate_win._get_dll_imports("random-lib-to-patch.dll")
    assert imports == ["test-random.dll"]


@pytest.mark.parametrize(("retval",), [[True], [False]])
def test_patch_dll(retval):
    with mock.patch("pefile.PE") as mock_pe:
        mock_pe.return_value = dllentry = mock.Mock(
            DIRECTORY_ENTRY_IMPORT=[
                mock.Mock(
                    dll=b"test-random.dll",
                    struct=mock.MagicMock(Name="test-random.dll"),
                )
            ]
        )
        dllentry.set_bytes_at_rva.return_value = retval

        result = consolidate_win._patch_dll(
            "test-random.dll", "test-replaced.dll", "libtopatch.dll"
        )
        assert result == retval

        dllentry.set_bytes_at_rva.assert_has_calls(
            [mock.call("test-random.dll", b"test-replaced.dll\x00")]
        )
