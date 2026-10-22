"""Types produced by the sandbox. No verdicts live here; A5 owns those."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class DenialClass(StrEnum):
    FILE_READ = "file-read"
    FILE_WRITE = "file-write"
    NETWORK = "network"
    LIMIT = "limit"
    PROCESS = "process"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class DenialRecord:
    kind: DenialClass
    detail: str


@dataclass(frozen=True)
class RunRecord:
    exit_code: int
    signal: int | None
    duration_s: float
    stdout: str
    stderr: str
    truncated: bool
    denials: tuple[DenialRecord, ...]
    limit_exceeded: str | None
    config_hash: str
    run_root: str
    started_at: str

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and self.signal is None and self.limit_exceeded is None


class SandboxError(RuntimeError):
    """Base class; callers map these to UNVERIFIED, never to a pass."""


class SandboxUnavailable(SandboxError):
    """No backend can confine on this platform. Nothing was executed."""


class SandboxFailed(SandboxError):
    """A backend was chosen but could not establish the jail. Nothing trustworthy ran."""
