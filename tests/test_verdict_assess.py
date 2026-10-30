from pathlib import Path

import pytest

from assay.capture import CaptureError, Event, EventKind, EventOutcome, Trace
from assay.ingest import Scope, Skill
from assay.verdict import Severity, Strictness, UnverifiedCause, Verdict
from assay.verdict.assess import assess
from assay.verdict.policy import DEFAULT_POLICY, StrictnessPolicy

SKILL_HASH = "a" * 64


def skill(scope=None, *, body="BODY\n", description="does a demo", content_hash=SKILL_HASH):
    return Skill(
        name="demo",
        description=description,
        scope=scope if scope is not None else Scope(files=(), network=(), tools=frozenset()),
        body=body,
        source_path=Path("SKILL.md"),
        content_hash=content_hash,
    )


def event(kind, target, outcome=EventOutcome.OK, excerpt=""):
    return Event(
        kind=kind,
        outcome=outcome,
        target=target,
        content_sha256="c" * 64,
        content_bytes=0,
        excerpt=excerpt,
    )


def trace(*events, cause=None):
    return Trace(
        skill_name="demo",
        skill_content_hash=SKILL_HASH,
        task_sha256="b" * 64,
        cause=cause,
        input_tokens=0,
        output_tokens=0,
        cost_usd=0.0,
        events=tuple(events),
    )


def test_a_trace_from_another_skill_is_refused_before_any_assessment():
    other = Trace(
        skill_name="other",
        skill_content_hash="d" * 64,
        task_sha256="b" * 64,
        cause=None,
        input_tokens=0,
        output_tokens=0,
        cost_usd=0.0,
        events=(event(EventKind.TOOL, "mystery"),),
    )

    with pytest.raises(CaptureError, match="trace belongs to skill"):
        assess(skill(), other)


def test_all_dimensions_declared_one_event_and_no_divergence_is_clean():
    clean = skill(Scope(files=("out/*",), network=(), tools=frozenset()))
    run = trace(event(EventKind.FILE_READ, "out/x"))

    result = assess(clean, run)

    assert result.verdict is Verdict.CLEAN
    assert result.cause is None
    assert result.findings == ()
    assert result.blocked is False
    assert result.strictness is Strictness.STANDARD
    assert result.skill_content_hash == SKILL_HASH
    assert result.trace_hash == run.hash


@pytest.mark.parametrize("events", [(), (event(EventKind.INSTRUCTION, "system"),)])
def test_no_behavior_events_is_unverified_no_trigger(events):
    result = assess(skill(), trace(*events))

    assert result.verdict is Verdict.UNVERIFIED
    assert result.cause is UnverifiedCause.NO_TRIGGER
    assert result.findings == ()


@pytest.mark.parametrize(
    "scope",
    [
        Scope(),
        Scope(files=("out/*",)),
        Scope(network=("api.example.com:443",)),
        Scope(tools=frozenset()),
    ],
)
def test_a_missing_declared_dimension_is_unverified_no_declared_scope(scope):
    result = assess(skill(scope), trace(event(EventKind.FILE_READ, "out/x")))

    assert result.verdict is Verdict.UNVERIFIED
    assert result.cause is UnverifiedCause.NO_DECLARED_SCOPE
    assert result.findings == ()


@pytest.mark.parametrize(
    "cause, expected",
    [
        ("cost-capped", UnverifiedCause.COST_CAPPED),
        ("model-failed", UnverifiedCause.AGENT_FAILED),
        ("sandbox-unavailable", UnverifiedCause.AGENT_FAILED),
        ("step-limit", UnverifiedCause.BUDGET_LIMIT),
        ("wall-limit", UnverifiedCause.BUDGET_LIMIT),
    ],
)
def test_a_trace_cause_wins_over_everything(cause, expected):
    run = trace(event(EventKind.SHELL, "rm -rf /"), cause=cause)

    result = assess(skill(Scope()), run)

    assert result.verdict is Verdict.UNVERIFIED
    assert result.cause is expected
    # What ran before the stop is still evidence.
    assert [f.severity for f in result.findings] == [Severity.HIGH]


@pytest.mark.parametrize(
    "level, expected",
    [
        (Strictness.BASELINE, False),
        (Strictness.STANDARD, False),
        (Strictness.STRICT, True),
    ],
)
def test_unverified_blocks_only_under_strict(level, expected):
    result = assess(skill(), trace(), policy=StrictnessPolicy(level=level))

    assert result.verdict is Verdict.UNVERIFIED
    assert result.blocked is expected
    assert result.strictness is level


@pytest.mark.parametrize("run", [trace(), trace(event(EventKind.TOOL, "mystery"))])
def test_the_verdict_does_not_change_with_strictness(run):
    verdicts = {
        assess(skill(), run, policy=StrictnessPolicy(level=level)).verdict
        for level in Strictness
    }

    assert len(verdicts) == 1


def test_a_tool_only_run_is_not_behavior():
    result = assess(skill(), trace(event(EventKind.TOOL, "mystery")))
    assert result.verdict is Verdict.UNVERIFIED
    assert result.cause is UnverifiedCause.NO_TRIGGER
