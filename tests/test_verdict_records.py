import pytest

from assay.capture import EventOutcome
from assay.verdict import (
    Assessment,
    Finding,
    FindingClass,
    Severity,
    Strictness,
    UnverifiedCause,
    Verdict,
    VerdictError,
)


def test_enums_are_the_closed_sets():
    assert {verdict.value for verdict in Verdict} == {
        "clean",
        "flagged",
        "malicious",
        "unverified",
    }
    assert {class_.value for class_ in FindingClass} == {
        "undeclared-file",
        "undeclared-network",
        "shell",
        "instructions",
    }
    assert {severity.value for severity in Severity} == {"low", "review", "high"}
    assert {cause.value for cause in UnverifiedCause} == {
        "no-trigger",
        "no-declared-scope",
        "agent-failed",
        "cost-capped",
    }
    assert {level.value for level in Strictness} == {"baseline", "standard", "strict"}
    assert issubclass(VerdictError, ValueError)


def test_severity_rank_orders_low_review_high():
    assert Severity.LOW.rank < Severity.REVIEW.rank < Severity.HIGH.rank
    assert [severity.rank for severity in Severity] == [0, 1, 2]


def test_finding_keeps_the_evidence_and_defaults_to_no_review():
    finding = Finding(
        class_=FindingClass.UNDECLARED_FILE,
        severity=Severity.REVIEW,
        target="out/x.txt",
        reason="file scope is declared empty",
        outcome=EventOutcome.OK,
    )

    assert finding.class_ is FindingClass.UNDECLARED_FILE
    assert finding.severity is Severity.REVIEW
    assert finding.target == "out/x.txt"
    assert finding.reason == "file scope is declared empty"
    assert finding.outcome is EventOutcome.OK
    assert finding.review_required is False


@pytest.mark.parametrize("over, field", [({"target": ""}, "target"), ({"reason": ""}, "reason")])
def test_finding_rejects_empty_text(over, field):
    base = dict(
        class_=FindingClass.UNDECLARED_FILE,
        severity=Severity.REVIEW,
        target="out/x.txt",
        reason="file scope is declared empty",
        outcome=EventOutcome.OK,
    )
    base.update(over)

    with pytest.raises(VerdictError, match=field):
        Finding(**base)


def assessment(**over):
    base = dict(
        verdict=Verdict.CLEAN,
        findings=(),
        cause=None,
        blocked=False,
        strictness=Strictness.STANDARD,
        skill_content_hash="a" * 64,
        trace_hash="b" * 64,
    )
    base.update(over)
    return Assessment(**base)


def test_assessment_requires_review_when_any_finding_does():
    reviewed = Finding(
        class_=FindingClass.INSTRUCTIONS,
        severity=Severity.REVIEW,
        target="exfiltrate",
        reason="instruction pattern matched",
        outcome=EventOutcome.OK,
        review_required=True,
    )

    assert assessment(findings=(reviewed,)).review_required is True
    assert assessment().review_required is False


@pytest.mark.parametrize(
    "verdict, cause",
    [
        (Verdict.UNVERIFIED, None),
        (Verdict.CLEAN, UnverifiedCause.NO_TRIGGER),
        (Verdict.FLAGGED, UnverifiedCause.AGENT_FAILED),
        (Verdict.MALICIOUS, UnverifiedCause.COST_CAPPED),
    ],
)
def test_unverified_iff_cause_is_set(verdict, cause):
    with pytest.raises(VerdictError):
        assessment(verdict=verdict, cause=cause)


def test_unverified_with_a_cause_is_valid():
    assert assessment(verdict=Verdict.UNVERIFIED, cause=UnverifiedCause.NO_TRIGGER)


@pytest.mark.parametrize(
    "over, field",
    [
        ({"skill_content_hash": "A" * 64}, "skill_content_hash"),
        ({"skill_content_hash": "a" * 63}, "skill_content_hash"),
        ({"trace_hash": "g" * 64}, "trace_hash"),
        ({"trace_hash": "b" * 65}, "trace_hash"),
    ],
)
def test_assessment_hashes_must_be_64_lowercase_hex(over, field):
    with pytest.raises(VerdictError, match=field):
        assessment(**over)


def test_assessment_findings_must_be_findings():
    with pytest.raises(VerdictError, match="findings"):
        assessment(findings=("not a finding",))


def test_assessment_blocked_must_be_a_bool():
    with pytest.raises(VerdictError, match="blocked"):
        assessment(blocked=1)
