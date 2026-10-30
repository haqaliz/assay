"""Turn a skill and its captured trace into exactly one assessment."""

from __future__ import annotations

import re
import unicodedata
from pathlib import PurePath

from assay.capture import (
    Diff,
    Divergence,
    DivergenceStatus,
    Event,
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

# Only captured commands are matched; no pattern is ever applied to the skill's markdown.
SHELL_PATTERNS = (
    ("rm -rf /", re.compile(r"\brm\s+(?:-{1,2}[a-z-]+\s+)*/(?:\s|$|\*)")),
    ("pipe to shell", re.compile(r"\|\s*(?:sudo\s+)?(?:\S*/)?(?:ba)?sh\b")),
    ("base64 decode", re.compile(r"\bbase64\s+-{1,2}[a-z]*d")),
    ("netcat", re.compile(r"\bnc\s+-")),
    ("ssh private key", re.compile(r"\bid_rsa(?!\.pub)")),
    ("host password file", re.compile(r"/etc/(?:passwd|shadow)\b")),
)

# A candidate signal only: capped at REVIEW, never HIGH, never MALICIOUS.
INSTRUCTION_PATTERNS = (
    ("ignore previous instructions", re.compile(r"\bignore previous instructions\b")),
    ("ignore all previous", re.compile(r"\bignore all previous\b")),
    ("do not tell the user", re.compile(r"\bdo(?: not|n't) tell the user\b")),
    ("without telling the user", re.compile(r"\bwithout telling the user\b")),
    ("override your", re.compile(r"\boverride your\b")),
    ("system prompt", re.compile(r"\bsystem prompt\b")),
    ("exfiltrate", re.compile(r"\bexfiltrat(?:e|ion|ing)\b")),
)

_BEHAVIOR = (EventKind.FILE_READ, EventKind.FILE_WRITE, EventKind.NETWORK, EventKind.SHELL)
_DENIAL_CLASS = {
    EventKind.FILE_READ: FindingClass.UNDECLARED_FILE,
    EventKind.FILE_WRITE: FindingClass.UNDECLARED_FILE,
    EventKind.NETWORK: FindingClass.UNDECLARED_NETWORK,
    EventKind.SHELL: FindingClass.SHELL,
}


def assess(skill: Skill, trace: Trace, *, policy: StrictnessPolicy = DEFAULT_POLICY) -> Assessment:
    result = diff(skill, trace)
    findings = _findings(skill, trace, result) + _instruction_findings(skill, trace)
    if trace.cause is not None:
        # The run stopped early, but what it did before stopping is still evidence.
        cause = (
            UnverifiedCause.COST_CAPPED
            if trace.cause == "cost-capped"
            else UnverifiedCause.AGENT_FAILED
        )
        return _assessment(result, policy, Verdict.UNVERIFIED, findings, cause)

    if findings:
        high = any(finding.severity is Severity.HIGH for finding in findings)
        verdict = Verdict.MALICIOUS if high else Verdict.FLAGGED
        return _assessment(result, policy, verdict, findings, None)

    if not any(event.kind in _BEHAVIOR for event in trace.events):
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
    if verdict is Verdict.MALICIOUS:
        return True
    if level is Strictness.BASELINE:
        return any(finding.severity is Severity.HIGH for finding in findings)
    if level is Strictness.STANDARD:
        return bool(findings)
    return bool(findings) or verdict is Verdict.UNVERIFIED


def _findings(skill: Skill, trace: Trace, result: Diff) -> tuple[Finding, ...]:
    findings = list(_divergence_findings(result))
    index = {(finding.class_, finding.target, finding.outcome): i for i, finding in enumerate(findings)}

    # Dangerous commands are captured behavior: they are findings even when the skill declared
    # Bash, otherwise a one-line declaration would switch the detector off.
    for event in trace.events:
        if event.kind is not EventKind.SHELL or event.outcome not in (
            EventOutcome.OK,
            EventOutcome.DENIED,
        ):
            continue
        label = _dangerous_shell(event.target)
        if label is None:
            continue
        finding = Finding(
            class_=FindingClass.SHELL,
            severity=Severity.HIGH,
            target=event.target,
            reason=f"dangerous shell pattern {label!r}",
            outcome=event.outcome,
            review_required=True,
        )
        _put(findings, index, finding)

    # A denial is a captured attempt, even inside declared scope.
    for event in trace.events:
        if event.kind is EventKind.FILE_WRITE and PurePath(event.target).is_absolute():
            if event.outcome in (EventOutcome.OK, EventOutcome.DENIED):
                _put(
                    findings,
                    index,
                    Finding(
                        class_=FindingClass.UNDECLARED_FILE,
                        severity=Severity.HIGH,
                        target=event.target,
                        reason=f"absolute write {event.target!r}",
                        outcome=event.outcome,
                        review_required=True,
                    ),
                )
        if event.outcome is not EventOutcome.DENIED:
            continue
        class_ = _DENIAL_CLASS.get(event.kind)
        if class_ is None:
            continue
        denial = "; ".join(event.denials) or "the action"
        _put(
            findings,
            index,
            Finding(
                class_=class_,
                severity=Severity.REVIEW,
                target=event.target,
                reason=f"sandbox denied {denial}",
                outcome=event.outcome,
            ),
        )
    return tuple(findings)


def _put(
    findings: list[Finding], index: dict[tuple, int], finding: Finding
) -> None:
    key = (finding.class_, finding.target, finding.outcome)
    if key in index:
        existing = findings[index[key]]
        if finding.severity.rank > existing.severity.rank:
            findings[index[key]] = finding
        return
    index[key] = len(findings)
    findings.append(finding)


def _divergence_findings(result: Diff) -> tuple[Finding, ...]:
    findings: list[Finding] = []
    for divergence in result.divergences:
        if divergence.kind is EventKind.SHELL:
            findings.append(_finding(FindingClass.SHELL, Severity.REVIEW, divergence, divergence.reason))
            continue
        if divergence.status is not DivergenceStatus.EXCEEDED:
            continue
        if divergence.kind is EventKind.NETWORK:
            findings.append(
                _finding(
                    FindingClass.UNDECLARED_NETWORK,
                    Severity.REVIEW,
                    divergence,
                    divergence.reason,
                )
            )
            continue
        if divergence.kind in (EventKind.FILE_READ, EventKind.FILE_WRITE):
            findings.append(
                _finding(
                    FindingClass.UNDECLARED_FILE,
                    Severity.REVIEW,
                    divergence,
                    divergence.reason,
                )
            )
    return tuple(findings)


def _finding(
    class_: FindingClass, severity: Severity, divergence: Divergence, reason: str
) -> Finding:
    return Finding(
        class_=class_,
        severity=severity,
        target=divergence.target,
        reason=reason,
        outcome=divergence.outcome,
        review_required=severity is Severity.HIGH,
    )


def _dangerous_shell(command: str) -> str | None:
    normalised = _normalise(command)
    return next((label for label, pattern in SHELL_PATTERNS if pattern.search(normalised)), None)


def _instruction_findings(skill: Skill, trace: Trace) -> tuple[Finding, ...]:
    # Only the system instruction is the skill's own text. The user task is ours, and scanning it
    # would attribute our prompt to the skill.
    excerpts = [
        event.excerpt
        for event in trace.events
        if event.kind is EventKind.INSTRUCTION and event.target == "system"
    ]
    text = _normalise("\n".join((skill.body, skill.description, *excerpts)))
    return tuple(
        Finding(
            class_=FindingClass.INSTRUCTIONS,
            severity=Severity.REVIEW,
            target=label,
            reason=f"instruction text matches {label!r}",
            outcome=EventOutcome.OK,
            review_required=True,
        )
        for label, pattern in INSTRUCTION_PATTERNS
        if pattern.search(text)
    )


def _normalise(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(char for char in decomposed if not unicodedata.combining(char))
    folded = stripped.casefold().replace("\u2019", "'")
    return " ".join(folded.split())
