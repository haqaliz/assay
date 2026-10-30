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
    BUDGET_LIMIT = "budget-limit"
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
        if not isinstance(self.class_, FindingClass):
            raise VerdictError(f"class_ must be a FindingClass, got {self.class_!r}")
        if not isinstance(self.severity, Severity):
            raise VerdictError(f"severity must be a Severity, got {self.severity!r}")
        if not isinstance(self.outcome, EventOutcome):
            raise VerdictError(f"outcome must be an EventOutcome, got {self.outcome!r}")
        for name in ("target", "reason"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise VerdictError(f"{name} must be a non-empty string, got {value!r}")
        if not isinstance(self.review_required, bool):
            raise VerdictError(
                f"review_required must be a bool, got {self.review_required!r}"
            )
        if self.severity is Severity.HIGH and not self.review_required:
            raise VerdictError("a HIGH finding must require review")
        if self.class_ is FindingClass.INSTRUCTIONS and self.severity is not Severity.REVIEW:
            raise VerdictError("an INSTRUCTIONS finding is capped at REVIEW")


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
        if not isinstance(self.verdict, Verdict):
            raise VerdictError(f"verdict must be a Verdict, got {self.verdict!r}")
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
        if self.verdict is Verdict.CLEAN and findings:
            raise VerdictError("CLEAN cannot carry findings")
        if self.verdict is Verdict.FLAGGED and (not findings or high):
            raise VerdictError("FLAGGED needs at least one finding and no HIGH finding")
        if self.verdict is Verdict.MALICIOUS and not high:
            raise VerdictError("MALICIOUS needs at least one HIGH finding")
        _hash64(self.skill_content_hash, "skill_content_hash")
        _hash64(self.trace_hash, "trace_hash")

    @property
    def review_required(self) -> bool:
        return any(finding.review_required for finding in self.findings)
