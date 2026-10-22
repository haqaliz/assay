import os
import signal
import sys
import time
from pathlib import Path

import pytest

from assay.sandbox import OUTPUT_CAP_BYTES, JailConfig, Limits, SandboxFailed
from assay.sandbox.seatbelt import SeatbeltSandbox

pytestmark = pytest.mark.skipif(sys.platform != "darwin", reason="Seatbelt is macOS-only")

PY = "/usr/bin/python3"


@pytest.fixture
def sandbox():
    return SeatbeltSandbox(Path("/usr/bin/sandbox-exec"))


def make_config(tmp_path, **over):
    root = tmp_path / "run"
    root.mkdir()
    over.setdefault("limits", Limits(wall_seconds=20.0))
    return JailConfig(run_root=root, **over)


def test_exit_code_and_stdout(sandbox, tmp_path):
    record = sandbox.run(["/bin/echo", "hi"], make_config(tmp_path))
    assert record.exit_code == 0
    assert record.stdout == "hi\n"
    assert record.signal is None
    assert record.ok
    assert record.config_hash.startswith("sha256:")


def test_cwd_is_the_run_root(sandbox, tmp_path):
    config = make_config(tmp_path)
    record = sandbox.run([PY, "-c", "import os; print(os.getcwd())"], config)
    assert record.stdout.strip() == str(config.run_root.resolve())


def test_env_is_scrubbed(sandbox, tmp_path, monkeypatch):
    monkeypatch.setenv("ASSAY_TEST_SECRET", "s3cr3t")
    record = sandbox.run(
        [PY, "-c", "import os; print(os.environ.get('ASSAY_TEST_SECRET', 'MISSING'));"
                   " print('PATH' if os.environ.get('PATH') else 'NOPATH')"],
        make_config(tmp_path),
    )
    assert "s3cr3t" not in record.stdout
    assert record.stdout.split() == ["MISSING", "PATH"]


def test_output_is_capped(sandbox, tmp_path):
    record = sandbox.run(
        [PY, "-c", "import sys; sys.stdout.write('x' * (2 * 1024 * 1024))"], make_config(tmp_path)
    )
    assert record.truncated
    assert len(record.stdout) == OUTPUT_CAP_BYTES


def test_wall_clock_kills_and_is_recorded(sandbox, tmp_path):
    config = make_config(tmp_path, limits=Limits(wall_seconds=1.0, cpu_seconds=30))
    record = sandbox.run(["/bin/sleep", "30"], config)
    assert record.limit_exceeded == "wall_seconds"
    assert record.duration_s < 10
    assert not record.ok


def test_cpu_limit_is_recorded(sandbox, tmp_path):
    config = make_config(tmp_path, limits=Limits(wall_seconds=20.0, cpu_seconds=1))
    record = sandbox.run([PY, "-c", "while True: pass"], config)
    assert record.limit_exceeded == "cpu_seconds"
    assert record.signal == signal.SIGXCPU


def test_run_root_is_removed_by_default(sandbox, tmp_path):
    config = make_config(tmp_path)
    sandbox.run(["/bin/echo", "hi"], config)
    assert not config.run_root.exists()


def test_keep_preserves_the_run_root(sandbox, tmp_path):
    config = make_config(tmp_path, keep=True)
    sandbox.run(["/bin/echo", "hi"], config)
    assert config.run_root.exists()


def test_no_orphan_survives(sandbox, tmp_path):
    record = sandbox.run(["/bin/sh", "-c", "sleep 60 & echo $!"], make_config(tmp_path))
    pid = int(record.stdout.strip())
    for _ in range(60):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        except PermissionError:
            return
        time.sleep(0.05)
    pytest.fail(f"orphan {pid} survived teardown")


def test_bad_profile_raises_sandbox_failed(sandbox, tmp_path, monkeypatch):
    monkeypatch.setattr("assay.sandbox.seatbelt.build_profile", lambda _config: "(bogus)")
    config = make_config(tmp_path)
    with pytest.raises(SandboxFailed, match="sandbox-exec"):
        sandbox.run(["/bin/echo", "hi"], config)
    assert not config.run_root.exists()


def test_teardown_failure_is_recorded(sandbox, tmp_path, monkeypatch):
    import shutil

    real_rmtree = shutil.rmtree
    calls = {"n": 0}

    def failing_once(path, *args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise OSError("boom")
        return real_rmtree(path, *args, **kwargs)

    monkeypatch.setattr("assay.sandbox.seatbelt.shutil.rmtree", failing_once)
    record = sandbox.run(["/bin/echo", "hi"], make_config(tmp_path))
    assert record.teardown_error is not None
    assert "run root" in record.teardown_error
    assert record.ok  # the run itself succeeded; the leak is reported, not hidden


def test_empty_argv_is_rejected(sandbox, tmp_path):
    with pytest.raises(ValueError, match="argv"):
        sandbox.run([], make_config(tmp_path))
