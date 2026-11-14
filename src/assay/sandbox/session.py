"""Long-lived sandbox session: spawn, line I/O, stderr capture, teardown."""

from __future__ import annotations

import os
import queue
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from .config import DEFAULT_PATH, OUTPUT_CAP_BYTES, JailConfig
from .denials import classify_failure
from .records import DenialRecord, SandboxFailed
from .process import _kill_group, _limit_setter, _remove_tree, _wait_quietly


class SessionError(RuntimeError):
    """The session transport failed."""


class SessionClosed(SessionError):
    """The session is closed or the process exited."""


class SessionTimeout(SessionError, TimeoutError):
    """A read deadline elapsed."""


@dataclass(frozen=True, slots=True)
class SessionRecord:
    exit_code: int | None
    signal: int | None
    stderr: str
    truncated: bool
    denials: tuple[DenialRecord, ...]
    config_hash: str
    run_root: str
    timed_out: bool
    teardown_error: str | None = None
    backend: str = ""
    network_mode: str = "none"


class SandboxSession:
    def __init__(
        self,
        command: Sequence[str],
        config: JailConfig,
        *,
        path: str = DEFAULT_PATH,
        setup_error_prefix: str = "sandbox-exec:",
        max_line_bytes: int = 1_048_576,
    ) -> None:
        if not command:
            raise ValueError("command must not be empty")
        if max_line_bytes <= 0:
            raise ValueError("max_line_bytes must be positive")
        self._command = [str(a) for a in command]
        self._config = config
        self._path = path
        self._setup_error_prefix = setup_error_prefix
        self._max_line_bytes = max_line_bytes
        self._proc: subprocess.Popen[bytes] | None = None
        self._stdout: queue.Queue[bytes | BaseException | None] = queue.Queue()
        self._stderr = bytearray()
        self._stderr_truncated = False
        self._stderr_lock = threading.Lock()
        self._stdout_thread: threading.Thread | None = None
        self._stderr_thread: threading.Thread | None = None
        self._record: SessionRecord | None = None
        self._timed_out = False

    def __enter__(self) -> "SandboxSession":
        if self._proc is not None:
            return self
        try:
            self._proc = subprocess.Popen(
                self._command,
                cwd=self._config.run_root,
                env={"PATH": self._path, **dict(self._config.env)},
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
                preexec_fn=_limit_setter(self._config.limits),
            )
        except OSError as exc:
            raise SandboxFailed(f"could not start sandbox: {exc}") from exc
        self._stdout_thread = threading.Thread(target=self._drain_stdout, daemon=True)
        self._stderr_thread = threading.Thread(target=self._drain_stderr, daemon=True)
        self._stdout_thread.start()
        self._stderr_thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @property
    def pid(self) -> int:
        if self._proc is None:
            raise SessionClosed("session was not started")
        return self._proc.pid

    @property
    def record(self) -> SessionRecord | None:
        return self._record

    def write_line(self, line: str) -> None:
        proc = self._proc
        if proc is None:
            raise SessionClosed("session was not started")
        if proc.poll() is not None:
            self._raise_if_dead()
        text = line.rstrip("\r\n")
        if "\n" in text or "\r" in text:
            raise SessionError("line must not contain a newline")
        data = (text + "\n").encode("utf-8")
        if len(data) > self._max_line_bytes:
            raise SessionError("line too long")
        assert proc.stdin is not None
        try:
            proc.stdin.write(data)
            proc.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            self._raise_if_dead()
            raise SessionClosed("stdin closed") from exc

    def read_line(self, deadline: float) -> str:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            self._timed_out = True
            raise SessionTimeout("deadline elapsed")
        try:
            item = self._stdout.get(timeout=remaining)
        except queue.Empty:
            self._timed_out = True
            raise SessionTimeout("deadline elapsed") from None
        if item is None:
            self._raise_if_dead()
            raise SessionClosed("stdout closed")
        if isinstance(item, BaseException):
            raise item
        return item.decode("utf-8", "replace").rstrip("\r\n")

    def close(self) -> SessionRecord:
        if self._record is not None:
            return self._record
        proc = self._proc
        if proc is None:
            raise SessionClosed("session was not started")

        teardown_error: str | None = None
        if proc.stdin is not None:
            try:
                proc.stdin.close()
            except OSError:
                pass
        try:
            proc.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            pass
        _kill_group(proc.pid)
        _wait_quietly(proc, timeout=5.0)
        if proc.poll() is None:
            try:
                proc.kill()
            except OSError:
                pass
            _wait_quietly(proc, timeout=2.0)

        for thread in (self._stdout_thread, self._stderr_thread):
            if thread is not None:
                thread.join(timeout=2.0)
        for stream in (proc.stdout, proc.stderr):
            if stream is not None:
                try:
                    stream.close()
                except OSError:
                    pass

        if not self._config.keep:
            teardown_error = _remove_tree(self._config.run_root)

        code = proc.returncode
        signal_number = -code if code is not None and code < 0 else None
        exit_code = code if code is not None and code >= 0 else None
        stderr = self._stderr_text()
        self._record = SessionRecord(
            exit_code=exit_code,
            signal=signal_number,
            stderr=stderr,
            truncated=self._stderr_truncated,
            denials=classify_failure(stderr),
            config_hash=self._config.config_hash,
            run_root=str(self._config.run_root),
            timed_out=self._timed_out,
            teardown_error=teardown_error,
            backend=self._config.backend,
            network_mode="port" if self._config.allow_network else "none",
        )
        return self._record

    def _drain_stdout(self) -> None:
        proc = self._proc
        assert proc is not None and proc.stdout is not None
        try:
            while True:
                line = proc.stdout.readline(self._max_line_bytes + 1)
                if not line:
                    break
                if len(line) > self._max_line_bytes:
                    self._stdout.put(SessionError("line too long"))
                    break
                self._stdout.put(line)
        finally:
            self._stdout.put(None)

    def _drain_stderr(self) -> None:
        proc = self._proc
        assert proc is not None and proc.stderr is not None
        fd = proc.stderr.fileno()
        while True:
            try:
                chunk = os.read(fd, 4096)
            except OSError:
                break
            if not chunk:
                break
            with self._stderr_lock:
                remaining = OUTPUT_CAP_BYTES - len(self._stderr)
                if remaining > 0:
                    self._stderr.extend(chunk[:remaining])
                if len(chunk) > remaining:
                    self._stderr_truncated = True

    def _stderr_text(self) -> str:
        with self._stderr_lock:
            return self._stderr.decode("utf-8", "replace")

    def _raise_if_dead(self) -> None:
        proc = self._proc
        if proc is None:
            raise SessionClosed("session was not started")
        code = proc.poll()
        stderr = self._stderr_text()
        failed = stderr.startswith(self._setup_error_prefix)
        if failed or (self._setup_error_prefix == "sandbox-exec:" and code in (65, 71)):
            name = self._setup_error_prefix.rstrip(":")
            raise SandboxFailed(
                f"{name} could not establish the jail (exit {code}): "
                f"{stderr.strip()[:200]}"
            )
        if code is not None:
            raise SessionClosed(f"process exited ({code})")
        raise SessionClosed("stdout closed")
