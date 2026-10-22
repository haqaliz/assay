import pytest

from assay.sandbox import SandboxUnavailable
from assay.sandbox.base import select_sandbox


def test_linux_fails_closed():
    with pytest.raises(SandboxUnavailable, match="linux"):
        select_sandbox(platform="linux")


@pytest.mark.parametrize("platform", ["win32", "freebsd", "emscripten", "linux2"])
def test_every_other_platform_fails_closed(platform):
    with pytest.raises(SandboxUnavailable):
        select_sandbox(platform=platform)


def test_darwin_without_sandbox_exec_fails_closed(tmp_path):
    with pytest.raises(SandboxUnavailable, match="sandbox-exec"):
        select_sandbox(platform="darwin", sandbox_exec=tmp_path / "missing")


def test_darwin_with_sandbox_exec_selects_seatbelt(tmp_path):
    from assay.sandbox.seatbelt import SeatbeltSandbox

    exe = tmp_path / "sandbox-exec"
    exe.write_text("")
    exe.chmod(0o755)
    assert isinstance(select_sandbox(platform="darwin", sandbox_exec=exe), SeatbeltSandbox)
