"""A server-shaped run and a conservative assessment. No CLEAN, no MALICIOUS."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from assay.agent.records import RunCause, RunOutcome
from assay.capture import Event, EventKind
from assay.sandbox.session import SessionRecord
from assay.verdict import (
    DEFAULT_POLICY,
    Finding,
    Severity,
    Strictness,
    StrictnessPolicy,
    UnverifiedCause,
    Verdict,
    VerdictError,
)

from .client import MCPTool
from .server import Server

_HEX = frozenset("0123456789abcdef")


def _hash64(value: object, name: str) -> None:
    if not isinstance(value, str) or len(value) != 64 or any(c not in _HEX for c in value):
        raise VerdictError(f"{name} must be 64 lowercase hex characters, got {value!r}")


@dataclass(frozen=True, slots=True)
class ServerRun:
    server: Server
    task: str
    tools: tuple[MCPTool, ...]
    events: tuple[Event, ...]
    findings: tuple[Finding, ...]
    outcome: RunOutcome
    session: SessionRecord

    def __post_init__(self) -> None:
        if not isinstance(self.task, str) or not self.task:
            raise ValueError("task must be a non-empty string")
        object.__setattr__(self, "tools", tuple(self.tools))
        object.__setattr__(self, "events", tuple(self.events))
        object.__setattr__(self, "findings", tuple(self.findings))

    @property
    def task_hash(self) -> str:
        return hashlib.sha256(self.task.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class ServerAssessment:
    server_name: str
    source_hash: str
    task_hash: str
    verdict: Verdict
    cause: UnverifiedCause | None
    findings: tuple[Finding, ...]
    strictness: Strictness
    blocked: bool

    def __post_init__(self) -> None:
        if not isinstance(self.server_name, str) or not self.server_name:
            raise VerdictError("server_name must be a non-empty string")
        _hash64(self.source_hash, "source_hash")
        _hash64(self.task_hash, "task_hash")
        if not isinstance(self.verdict, Verdict):
            raise VerdictError(f"verdict must be a Verdict, got {self.verdict!r}")
        if self.verdict not in (Verdict.UNVERIFIED, Verdict.FLAGGED):
            raise VerdictError(
                "a server assessment cannot be CLEAN or MALICIOUS; "
                "a manifest declares startup, not behavior"
            )
        if not isinstance(self.strictness, Strictness):
            raise VerdictError(f"strictness must be a Strictness, got {self.strictness!r}")
        if self.cause is not None and not isinstance(self.cause, UnverifiedCause):
            raise VerdictError(f"cause must be an UnverifiedCause or None, got {self.cause!r}")
        if not isinstance(self.blocked, bool):
            raise VerdictError(f"blocked must be a bool, got {self.blocked!r}")
        findings = tuple(self.findings)
        if not all(isinstance(finding, Finding) for finding in findings):
            raise VerdictError("findings must be Finding records")
        object.__setattr__(self, "findings", findings)
        if (self.verdict is Verdict.UNVERIFIED) != (self.cause is not None):
            raise VerdictError(
                "verdict UNVERIFIED iff cause is set, "
                f"got verdict={self.verdict!r} cause={self.cause!r}"
            )
        high = any(finding.severity is Severity.HIGH for finding in findings)
        if self.verdict is Verdict.FLAGGED and (not findings or high):
            raise VerdictError("FLAGGED needs at least one finding and no HIGH finding")

    def to_payload(self) -> dict[str, object]:
        return {
            "server_name": self.server_name,
            "source_hash": self.source_hash,
            "task_hash": self.task_hash,
            "verdict": self.verdict.value,
            "cause": self.cause.value if self.cause is not None else None,
            "findings": [finding.to_payload() for finding in self.findings],
            "strictness": self.strictness.value,
            "blocked": self.blocked,
        }


def assess_server(
    run: ServerRun, *, policy: StrictnessPolicy = DEFAULT_POLICY
) -> ServerAssessment:
    findings = run.findings
    cause = run.outcome.cause
    if cause is not None:
        verdict = Verdict.UNVERIFIED
        mapped = _cause(cause)
    elif findings:
        verdict = Verdict.FLAGGED
        mapped = None
    elif not any(event.kind is EventKind.TOOL for event in run.events):
        verdict = Verdict.UNVERIFIED
        mapped = UnverifiedCause.NO_TRIGGER
    else:
        verdict = Verdict.UNVERIFIED
        mapped = UnverifiedCause.NO_DECLARED_SCOPE
    return ServerAssessment(
        server_name=run.server.name,
        source_hash=run.server.source_hash,
        task_hash=run.task_hash,
        verdict=verdict,
        cause=mapped,
        findings=findings,
        strictness=policy.level,
        blocked=_blocked(verdict, findings, policy.level),
    )


def _cause(cause: RunCause) -> UnverifiedCause:
    if cause is RunCause.COST_CAPPED:
        return UnverifiedCause.COST_CAPPED
    if cause in (RunCause.STEP_LIMIT, RunCause.ACTION_LIMIT, RunCause.WALL_LIMIT):
        return UnverifiedCause.BUDGET_LIMIT
    return UnverifiedCause.AGENT_FAILED


def _blocked(
    verdict: Verdict, findings: tuple[Finding, ...], level: Strictness
) -> bool:
    if level is Strictness.BASELINE:
        return any(finding.severity is Severity.HIGH for finding in findings)
    if level is Strictness.STANDARD:
        return bool(findings)
    return bool(findings) or verdict is Verdict.UNVERIFIED
