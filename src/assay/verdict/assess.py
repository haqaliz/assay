"""Turn a skill and its captured trace into exactly one assessment."""

from __future__ import annotations

from assay.capture import EventKind, Trace, diff
from assay.ingest import Skill

from .policy import DEFAULT_POLICY, StrictnessPolicy
from .records import Assessment, Finding, Severity, Strictness, UnverifiedCause, Verdict


def _blocked(verdict: Verdict, findings: tuple[Finding, ...], level: Strictness) -> bool:
    if level is Strictness.BASELINE:
        return any(finding.severity is Severity.HIGH for finding in findings)
    if level is Strictness.STANDARD:
        return bool(findings)
    return bool(findings) or verdict is Verdict.UNVERIFIED


def assess(skill: Skill, trace: Trace, *, policy: StrictnessPolicy = DEFAULT_POLICY) -> Assessment:
    result = diff(skill, trace)
    if trace.cause is not None:
        cause = (
            UnverifiedCause.COST_CAPPED
            if trace.cause == "cost-capped"
            else UnverifiedCause.AGENT_FAILED
        )
        verdict = Verdict.UNVERIFIED
    elif not any(change.kind is not EventKind.INSTRUCTION for change in trace.events):
        verdict, cause = Verdict.UNVERIFIED, UnverifiedCause.NO_TRIGGER
    elif skill.scope.files is None or skill.scope.network is None or skill.scope.tools is None:
        verdict, cause = Verdict.UNVERIFIED, UnverifiedCause.NO_DECLARED_SCOPE
    else:
        verdict, cause = Verdict.CLEAN, None
    return Assessment(
        verdict=verdict,
        findings=(),
        cause=cause,
        blocked=_blocked(verdict, (), policy.level),
        strictness=policy.level,
        skill_content_hash=result.skill_content_hash,
        trace_hash=result.trace_hash,
    )
