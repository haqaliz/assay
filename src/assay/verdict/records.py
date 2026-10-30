"""Types produced by the verdict layer. A5 owns the only verdict in the engine."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from assay.capture import EventOutcome

_HEX = frozenset("0123456789abcdef")


def _hash64(value: object, name: str) -> None:
    if not isinstance(value, str) or len(value) != 64 or any(c not in _HEX for c in value):
        raise VerdictError(f"{name} must be 64 lowercase hex characters, got {value!r}")


class VerdictError(ValueError):
    """An assessment or policy is invalid; never a verdict."""


class Verdict(StrEnum):
    CLEAN = "clean"
    FLAGGED = "flagged"
    MALICIOUS = "malicious"
    UNVERIFIED = "unverified"


class FindingClass(StrEnum):
    UNDECLARED_FILE = "undeclared-file"
    UNDECLARED_NETWORK = "undeclared-network"
    SHELL = "shell"
    INSTRUCTIONS = "instructions"


class Severity(StrEnum):
    LOW = "low"
    REVIEW = "review"
    HIGH = "high"

    @property
    def rank(self) -> int:
        return _SEVERITY_RANK[self]


_SEVERITY_RANK = {Severity.LOW: 0, Severity.REVIEW: 1, Severity.HIGH: 2}


class UnverifiedCause(StrEnum):
    NO_TRIGGER = "no-trigger"
    NO_DECLARED_SCOPE = "no-declared-scope"
    AGENT_FAILED = "agent-failed"
    COST_CAPPED = "cost-capped"


class Strictness(StrEnum):
    BASELINE = "baseline"
    STANDARD = "standard"
    STRICT = "strict"


@dataclass(frozen=True, slots=True)
class Finding:
    class_: FindingClass
    severity: Severity
    target: str
    reason: str
    outcome: EventOutcome
    review_required: bool = False

    def __post_init__(self) -> None:
        for name in ("target", "reason"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise VerdictError(f"{name} must be a non-empty string, got {value!r}")
        if not isinstance(self.review_required, bool):
            raise VerdictError(
                f"review_required must be a bool, got {self.review_required!r}"
            )


@dataclass(frozen=True, slots=True)
class Assessment:
    verdict: Verdict
    findings: tuple[Finding, ...]
    cause: UnverifiedCause | None
    blocked: bool
    strictness: Strictness
    skill_content_hash: str
    trace_hash: str

    def __post_init__(self) -> None:
        if (self.verdict is Verdict.UNVERIFIED) != (self.cause is not None):
            raise VerdictError(
                "verdict UNVERIFIED iff cause is set, "
                f"got verdict={self.verdict!r} cause={self.cause!r}"
            )
        _hash64(self.skill_content_hash, "skill_content_hash")
        _hash64(self.trace_hash, "trace_hash")
        if not all(isinstance(finding, Finding) for finding in self.findings):
            raise VerdictError("findings must be Finding records")
        if not isinstance(self.blocked, bool):
            raise VerdictError(f"blocked must be a bool, got {self.blocked!r}")

    @property
    def review_required(self) -> bool:
        return any(finding.review_required for finding in self.findings)
