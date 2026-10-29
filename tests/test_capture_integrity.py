"""The capture channel must not be writable by the child it captures."""

import sys

import pytest

from assay.sandbox.config import JailConfig
from assay.sandbox.records import SandboxFailed
from assay.sandbox.seatbelt import SeatbeltSandbox

pytestmark = pytest.mark.skipif(sys.platform != "darwin", reason="Seatbelt is macOS-only")

SANDBOX_EXEC = "/usr/bin/sandbox-exec"


def test_child_cannot_erase_or_forge_its_own_capture(tmp_path):
    config = JailConfig(run_root=tmp_path)
    record = SeatbeltSandbox(SANDBOX_EXEC).run(
        ["/bin/sh", "-c", "echo forged > .assay/stdout; echo done"], config
    )
    assert "forged" not in record.stdout
    assert record.stdout.strip() == "done"


def test_child_cannot_remove_the_capture_directory(tmp_path):
    config = JailConfig(run_root=tmp_path, keep=True)
    record = SeatbeltSandbox(SANDBOX_EXEC).run(["/bin/sh", "-c", "rmdir .assay"], config)
    assert not record.ok
    assert (tmp_path / ".assay").is_dir()


def test_capture_directory_that_is_a_file_fails_closed(tmp_path):
    (tmp_path / ".assay").write_text("not a directory")
    with pytest.raises(SandboxFailed):
        SeatbeltSandbox(SANDBOX_EXEC).run(["/bin/true"], JailConfig(run_root=tmp_path))


def test_capture_directory_that_is_a_symlink_fails_closed(tmp_path):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (tmp_path / "run").mkdir()
    (tmp_path / "run" / ".assay").symlink_to(elsewhere)
    with pytest.raises(SandboxFailed):
        SeatbeltSandbox(SANDBOX_EXEC).run(
            ["/bin/true"], JailConfig(run_root=tmp_path / "run")
        )
    assert list(elsewhere.iterdir()) == []
