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

FINDING_FIELDS = {"class", "severity", "target", "reason", "outcome", "review_required"}
ASSESSMENT_FIELDS = {
    "verdict",
    "cause",
    "blocked",
    "strictness",
    "findings",
    "skill_content_hash",
    "trace_hash",
}


def finding(**over):
    base = dict(
        class_=FindingClass.UNDECLARED_NETWORK,
        severity=Severity.REVIEW,
        target="https://example.test/x",
        reason="network scope is declared empty",
        outcome=EventOutcome.OK,
    )
    base.update(over)
    return Finding(**base)


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


def test_finding_payload_has_the_cli_field_names():
    payload = finding(review_required=True).to_payload()

    assert set(payload) == FINDING_FIELDS
    assert payload == {
        "class": "undeclared-network",
        "severity": "review",
        "target": "https://example.test/x",
        "reason": "network scope is declared empty",
        "outcome": "ok",
        "review_required": True,
    }


@pytest.mark.parametrize(
    "original",
    [
        finding(),
        finding(
            class_=FindingClass.SHELL,
            severity=Severity.HIGH,
            target="rm -rf /",
            reason="dangerous shell pattern 'rm -rf /'",
            outcome=EventOutcome.DENIED,
            review_required=True,
        ),
    ],
    ids=["review", "high"],
)
def test_finding_payload_round_trips(original):
    assert Finding.from_payload(original.to_payload()) == original


@pytest.mark.parametrize(
    "original",
    [
        assessment(),
        assessment(
            verdict=Verdict.FLAGGED,
            findings=(finding(),),
            blocked=True,
            strictness=Strictness.STRICT,
        ),
        assessment(
            verdict=Verdict.UNVERIFIED,
            cause=UnverifiedCause.NO_TRIGGER,
            blocked=True,
        ),
    ],
    ids=["clean", "flagged", "unverified"],
)
def test_assessment_payload_round_trips(original):
    assert Assessment.from_payload(original.to_payload()) == original


def test_assessment_payload_field_set():
    payload = assessment(verdict=Verdict.FLAGGED, findings=(finding(),)).to_payload()

    assert set(payload) == ASSESSMENT_FIELDS
    assert payload["findings"] == [finding().to_payload()]
    assert payload["cause"] is None
    assert payload["skill_content_hash"] == "a" * 64
    assert payload["trace_hash"] == "b" * 64


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param(
            {k: v for k, v in assessment().to_payload().items() if k != "strictness"},
            id="missing-key",
        ),
        pytest.param({**assessment().to_payload(), "verdict": "maybe"}, id="bad-enum"),
        pytest.param({**assessment().to_payload(), "cause": "not-a-cause"}, id="bad-cause"),
        pytest.param(
            {**assessment().to_payload(), "verdict": "unverified"},
            id="unverified-without-cause",
        ),
        pytest.param(
            {**assessment().to_payload(), "verdict": "flagged", "findings": []},
            id="flagged-without-findings",
        ),
        pytest.param(
            {**assessment().to_payload(), "findings": [finding().to_payload()]},
            id="clean-with-findings",
        ),
    ],
)
def test_assessment_from_payload_refuses_missing_or_bad_fields(payload):
    with pytest.raises(VerdictError):
        Assessment.from_payload(payload)


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param({"class": "undeclared-file"}, id="missing-key"),
        pytest.param({**finding().to_payload(), "class": "not-a-class"}, id="bad-enum"),
        pytest.param({**finding().to_payload(), "outcome": 1}, id="wrong-type"),
        pytest.param(
            {**finding().to_payload(), "severity": "high", "review_required": False},
            id="invariant-violation",
        ),
    ],
)
def test_finding_from_payload_refuses_missing_or_bad_fields(payload):
    with pytest.raises(VerdictError):
        Finding.from_payload(payload)
