"""Turn a skill and its captured trace into exactly one assessment."""

from __future__ import annotations

from pathlib import PurePath

from assay.capture import (
    Diff,
    Divergence,
    DivergenceStatus,
    EventKind,
    EventOutcome,
    Trace,
    diff,
)
from assay.ingest import Skill

from .policy import DEFAULT_POLICY, StrictnessPolicy
from .records import (
    Assessment,
    Finding,
    FindingClass,
    Severity,
    Strictness,
    UnverifiedCause,
    Verdict,
)

SHELL_PATTERNS = ("rm -rf /", "| sh", "| bash", "base64 -d", "nc -", "id_rsa", "/etc/passwd")
INSTRUCTION_PATTERNS = (
    "ignore previous instructions",
    "ignore all previous",
    "do not tell the user",
    "don't tell the user",
    "without telling",
    "override your",
    "system prompt",
    "exfiltrate",
)


def assess(skill: Skill, trace: Trace, *, policy: StrictnessPolicy = DEFAULT_POLICY) -> Assessment:
    result = diff(skill, trace)
    if trace.cause is not None:
        cause = (
            UnverifiedCause.COST_CAPPED
            if trace.cause == "cost-capped"
            else UnverifiedCause.AGENT_FAILED
        )
        return _assessment(result, policy, Verdict.UNVERIFIED, (), cause)

    findings = _findings(result, policy) + _instruction_findings(skill, trace)
    if findings:
        high = any(finding.severity is Severity.HIGH for finding in findings)
        verdict = Verdict.MALICIOUS if high else Verdict.FLAGGED
        return _assessment(result, policy, verdict, findings, None)

    if not any(change.kind is not EventKind.INSTRUCTION for change in trace.events):
        verdict, cause = Verdict.UNVERIFIED, UnverifiedCause.NO_TRIGGER
    elif skill.scope.files is None or skill.scope.network is None or skill.scope.tools is None:
        verdict, cause = Verdict.UNVERIFIED, UnverifiedCause.NO_DECLARED_SCOPE
    else:
        verdict, cause = Verdict.CLEAN, None
    return _assessment(result, policy, verdict, (), cause)


def _assessment(
    result: Diff,
    policy: StrictnessPolicy,
    verdict: Verdict,
    findings: tuple[Finding, ...],
    cause: UnverifiedCause | None,
) -> Assessment:
    return Assessment(
        verdict=verdict,
        findings=findings,
        cause=cause,
        blocked=_blocked(verdict, findings, policy.level),
        strictness=policy.level,
        skill_content_hash=result.skill_content_hash,
        trace_hash=result.trace_hash,
    )


def _blocked(verdict: Verdict, findings: tuple[Finding, ...], level: Strictness) -> bool:
    if level is Strictness.BASELINE:
        return any(finding.severity is Severity.HIGH for finding in findings)
    if level is Strictness.STANDARD:
        return bool(findings)
    return bool(findings) or verdict is Verdict.UNVERIFIED


def _findings(result: Diff, policy: StrictnessPolicy) -> tuple[Finding, ...]:
    findings: list[Finding] = []
    for divergence in result.divergences:
        if divergence.kind is EventKind.SHELL:
            base = Severity.REVIEW
            reason = divergence.reason
            if divergence.outcome in (EventOutcome.OK, EventOutcome.DENIED):
                pattern = next(
                    (item for item in SHELL_PATTERNS if item in divergence.target.lower()),
                    None,
                )
                if pattern is not None:
                    base = Severity.HIGH
                    reason = f"{divergence.reason}; dangerous shell pattern {pattern!r}"
            findings.append(_finding(FindingClass.SHELL, base, divergence, policy, reason))
            continue
        if divergence.status is not DivergenceStatus.EXCEEDED:
            continue
        if divergence.kind is EventKind.NETWORK:
            findings.append(
                _finding(
                    FindingClass.UNDECLARED_NETWORK,
                    Severity.REVIEW,
                    divergence,
                    policy,
                    divergence.reason,
                )
            )
            continue
        if divergence.kind not in (EventKind.FILE_READ, EventKind.FILE_WRITE):
            continue
        base = Severity.REVIEW
        reason = divergence.reason
        if (
            divergence.kind is EventKind.FILE_WRITE
            and PurePath(divergence.target).is_absolute()
            and divergence.outcome in (EventOutcome.OK, EventOutcome.DENIED)
        ):
            base = Severity.HIGH
            reason = f"{divergence.reason}; absolute write {divergence.target!r}"
        findings.append(_finding(FindingClass.UNDECLARED_FILE, base, divergence, policy, reason))
    return tuple(findings)


def _finding(
    class_: FindingClass,
    base: Severity,
    divergence: Divergence,
    policy: StrictnessPolicy,
    reason: str,
) -> Finding:
    severity = _effective(base, class_, policy, divergence.outcome)
    return Finding(
        class_=class_,
        severity=severity,
        target=divergence.target,
        reason=reason,
        outcome=divergence.outcome,
        review_required=severity is Severity.HIGH,
    )


def _effective(
    base: Severity, class_: FindingClass, policy: StrictnessPolicy, outcome: EventOutcome
) -> Severity:
    floor = policy.floor(class_)
    severity = floor if floor.rank > base.rank else base
    # A failed attempt is not the captured success MALICIOUS claims; the floor stops at REVIEW.
    if outcome is EventOutcome.FAILED and severity is Severity.HIGH:
        return Severity.REVIEW
    return severity


def _instruction_findings(skill: Skill, trace: Trace) -> tuple[Finding, ...]:
    excerpts = [event.excerpt for event in trace.events if event.kind is EventKind.INSTRUCTION]
    text = "\n".join((skill.body, skill.description, *excerpts)).lower()
    # One finding per pattern; the body is authoritative and an excerpt only proves delivery.
    return tuple(
        Finding(
            class_=FindingClass.INSTRUCTIONS,
            severity=Severity.REVIEW,
            target=pattern,
            reason=f"instruction text matches {pattern!r}",
            outcome=EventOutcome.OK,
            review_required=True,
        )
        for pattern in INSTRUCTION_PATTERNS
        if pattern in text
    )
