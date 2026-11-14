"""Shared POSIX process runner for sandbox backends."""

from __future__ import annotations

import os
import resource
import shutil
import signal
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Sequence

from .config import OUTPUT_CAP_BYTES, JailConfig, Limits
from .denials import classify_failure
from .records import RunRecord, SandboxFailed

SetupError = Callable[[int, str], str | None]


def run_process(
    command: Sequence[str],
    config: JailConfig,
    *,
    path: str,
    start_error: str,
    setup_error: SetupError,
) -> RunRecord:
    """Run one already-confined command and capture its result."""
    if not command:
        raise ValueError("command must not be empty")
    out_dir = config.run_root / ".assay"
    if out_dir.is_symlink():
        raise SandboxFailed(f"capture directory {out_dir} must not be a symlink")
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise SandboxFailed(f"cannot create capture directory {out_dir}: {exc}") from None
    # shortcut: the child can still write through the inherited stdout/stderr file descriptors;
    # the backend's read-only bind/profile protects the paths, not the descriptors. A4 owns
    # trustworthy capture via the mediated tool surface.
    stdout_path, stderr_path = out_dir / "stdout", out_dir / "stderr"
    limits = config.limits

    started = time.monotonic()
    started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    limit_exceeded: str | None = None
    teardown_error: str | None = None
    proc: subprocess.Popen[bytes] | None = None

    try:
        try:
            with open(stdout_path, "wb") as out, open(stderr_path, "wb") as err:
                proc = subprocess.Popen(
                    [str(a) for a in command],
                    cwd=config.run_root,
                    env={"PATH": path, **dict(config.env)},
                    stdin=subprocess.DEVNULL,
                    stdout=out,
                    stderr=err,
                    start_new_session=True,
                    preexec_fn=_limit_setter(limits),
                )
                try:
                    proc.wait(timeout=limits.wall_seconds)
                except subprocess.TimeoutExpired:
                    limit_exceeded = "wall_seconds"
                    _kill_group(proc.pid)
                    _wait_quietly(proc, timeout=5.0)
        except OSError as exc:
            raise SandboxFailed(f"could not start {start_error}: {exc}") from exc

        duration = time.monotonic() - started
        returncode = proc.returncode if proc.returncode is not None else -signal.SIGKILL
        sig = -returncode if returncode < 0 else None
        if sig is not None and limit_exceeded is None:
            limit_exceeded = {
                signal.SIGXCPU: "cpu_seconds",
                signal.SIGXFSZ: "file_bytes",
            }.get(sig)
        exit_code = returncode if returncode >= 0 else 128 + (-returncode)

        stdout, out_truncated = _read_capped(stdout_path)
        stderr, err_truncated = _read_capped(stderr_path)

        failure = setup_error(returncode, stderr)
        if failure is not None:
            raise SandboxFailed(failure)
    finally:
        if proc is not None:
            _kill_group(proc.pid)
        if not config.keep:
            teardown_error = _remove_tree(config.run_root)

    return RunRecord(
        exit_code=exit_code,
        signal=sig,
        duration_s=duration,
        stdout=stdout,
        stderr=stderr,
        truncated=out_truncated or err_truncated,
        denials=classify_failure(f"{stdout}\n{stderr}", limit_exceeded),
        limit_exceeded=limit_exceeded,
        config_hash=config.config_hash,
        run_root=str(config.run_root),
        started_at=started_at,
        teardown_error=teardown_error,
        backend=config.backend,
        network_mode="port" if config.allow_network else "none",
    )


def _limit_setter(limits: Limits) -> Callable[[], None]:
    def apply() -> None:
        # RLIMIT_NPROC is deliberately absent: it counts the UID's processes host-wide, so a low
        # cap leaves the child unable to fork at all (probed on a 380-process host).
        resource.setrlimit(resource.RLIMIT_CPU, (limits.cpu_seconds, limits.cpu_seconds))
        resource.setrlimit(resource.RLIMIT_FSIZE, (limits.file_bytes, limits.file_bytes))

    return apply


def _kill_group(pid: int) -> None:
    try:
        os.killpg(pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


def _wait_quietly(proc: subprocess.Popen[bytes], timeout: float) -> None:
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        pass


def _read_capped(path: Path) -> tuple[str, bool]:
    try:
        with open(path, "rb") as fh:
            data = fh.read(OUTPUT_CAP_BYTES + 1)
    except OSError:
        return "", False
    truncated = len(data) > OUTPUT_CAP_BYTES
    return data[:OUTPUT_CAP_BYTES].decode("utf-8", "replace"), truncated


def _remove_tree(root: Path) -> str | None:
    try:
        shutil.rmtree(root)
        return None
    except FileNotFoundError:
        return None
    except OSError as exc:
        try:
            shutil.rmtree(root, ignore_errors=True)
        except OSError:
            pass
        return f"run root not fully removed: {root}: {exc}"
