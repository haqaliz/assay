import os
import time

import pytest

from assay.sandbox import JailConfig, Limits
from assay.sandbox.records import SandboxFailed
from assay.sandbox.session import (
    SandboxSession,
    SessionClosed,
    SessionError,
    SessionTimeout,
)

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
FAKE = os.path.join(FIXTURES, "fake_sandbox_exec.sh")
FAIL = os.path.join(FIXTURES, "fake_sandbox_fail.sh")


def make_config(tmp_path, *, keep=False):
    root = tmp_path / "run"
    root.mkdir()
    return JailConfig(run_root=root, limits=Limits(wall_seconds=10.0), keep=keep)


def test_write_and_read_a_line(tmp_path):
    config = make_config(tmp_path)
    argv = [
        "/bin/sh",
        "-c",
        "while IFS= read -r line; do printf 'echo:%s\\n' \"$line\"; done",
    ]

    with SandboxSession(FAKE, argv, config) as session:
        session.write_line("hello")
        assert session.read_line(time.monotonic() + 2) == "echo:hello"
        record = session.close()

    assert record.exit_code == 0
    assert record.timed_out is False
    assert record.teardown_error is None
    assert record.config_hash == config.config_hash
    assert record.run_root == str(config.run_root)
    assert not config.run_root.exists()


def test_read_line_times_out(tmp_path):
    config = make_config(tmp_path)

    with SandboxSession(FAKE, ["/bin/cat"], config) as session:
        with pytest.raises(SessionTimeout):
            session.read_line(time.monotonic() + 0.1)
        record = session.close()

    assert record.timed_out is True


def test_close_is_idempotent(tmp_path):
    config = make_config(tmp_path)
    session = SandboxSession(FAKE, ["/bin/cat"], config)
    session.__enter__()

    first = session.close()
    second = session.close()

    assert first is second
    assert session.record is first


def test_dead_process_raises_session_closed(tmp_path):
    config = make_config(tmp_path)
    session = SandboxSession(FAKE, ["/bin/true"], config)
    session.__enter__()

    with pytest.raises(SessionClosed):
        session.read_line(time.monotonic() + 2)
    session.close()


def test_sandbox_exec_failure_raises_sandbox_failed(tmp_path):
    config = make_config(tmp_path)

    with pytest.raises(SandboxFailed, match="sandbox-exec"):
        with SandboxSession(FAIL, ["/bin/true"], config) as session:
            session.read_line(time.monotonic() + 2)


def test_close_kills_the_process_group(tmp_path):
    config = make_config(tmp_path)
    session = SandboxSession(FAKE, ["/bin/sh", "-c", "sleep 60 & echo $!"], config)
    session.__enter__()

    pid = int(session.read_line(time.monotonic() + 2))
    session.close()

    for _ in range(60):
        try:
            os.kill(pid, 0)
        except (ProcessLookupError, PermissionError):
            return
        time.sleep(0.05)
    pytest.fail(f"orphan {pid} survived teardown")


def test_keep_preserves_the_run_root(tmp_path):
    config = make_config(tmp_path, keep=True)

    with SandboxSession(FAKE, ["/bin/cat"], config) as session:
        session.close()

    assert config.run_root.exists()


def test_write_line_rejects_an_oversized_line(tmp_path):
    config = make_config(tmp_path)

    with SandboxSession(FAKE, ["/bin/cat"], config, max_line_bytes=8) as session:
        with pytest.raises(SessionError, match="too long"):
            session.write_line("x" * 9)


def test_read_line_rejects_an_oversized_line(tmp_path):
    config = make_config(tmp_path)
    argv = ["/bin/sh", "-c", "printf '%100s\\n' x"]

    with SandboxSession(FAKE, argv, config, max_line_bytes=8) as session:
        with pytest.raises(SessionError, match="too long"):
            session.read_line(time.monotonic() + 2)
