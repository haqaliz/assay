import hashlib
from pathlib import Path

import pytest

from assay.agent import RunCause, RunOutcome, Usage
from assay.capture import EventOutcome
from assay.mcp.assess import ServerAssessment, ServerRun, assess_server
from assay.mcp.client import MCPResult, MCPTool
from assay.mcp.events import event_for_call
from assay.mcp.server import Server
from assay.sandbox.session import SessionRecord
from assay.verdict import (
    Finding,
    FindingClass,
    Severity,
    Strictness,
    StrictnessPolicy,
    UnverifiedCause,
    Verdict,
    VerdictError,
)

RECORD = SessionRecord(
    exit_code=0,
    signal=None,
    stderr="",
    truncated=False,
    denials=(),
    config_hash="sha256:" + "a" * 64,
    run_root="/tmp/run",
    timed_out=False,
)


def server():
    return Server(
        name="demo",
        command="python3",
        args=("-u", "server.py"),
        source_path=Path("mcp.json"),
        source_hash="b" * 64,
    )


def tool(name="echo"):
    return MCPTool(name=name, description="Echo.", input_schema={"type": "object"})


def call_event(name="echo", text="hello"):
    return event_for_call(name, {}, MCPResult(ok=True, text=text))


def finding():
    return Finding(
        class_=FindingClass.INSTRUCTIONS,
        severity=Severity.REVIEW,
        target="tool:echo",
        reason="tool description matches 'ignore the above'",
        outcome=EventOutcome.OK,
        review_required=True,
    )


def outcome(cause=None):
    return RunOutcome(
        cause=cause,
        final_text=None,
        steps=1,
        actions=(),
        usage=Usage(),
        cost_usd=0.0,
    )


def run(*events, findings=(), cause=None):
    return ServerRun(
        server=server(),
        task="do the task",
        tools=(tool(),),
        events=tuple(events),
        findings=tuple(findings),
        outcome=outcome(cause),
        session=RECORD,
    )


def test_no_events_is_no_trigger():
    result = assess_server(run())

    assert result.verdict is Verdict.UNVERIFIED
    assert result.cause is UnverifiedCause.NO_TRIGGER
    assert result.findings == ()
    assert result.blocked is False


def test_calls_without_findings_are_no_declared_scope():
    result = assess_server(run(call_event()))

    assert result.verdict is Verdict.UNVERIFIED
    assert result.cause is UnverifiedCause.NO_DECLARED_SCOPE
    assert result.findings == ()


def test_a_review_finding_is_flagged_and_blocked_under_standard():
    result = assess_server(run(call_event(), findings=(finding(),)))

    assert result.verdict is Verdict.FLAGGED
    assert result.cause is None
    assert result.findings == (finding(),)
    assert result.blocked is True
    assert result.strictness is Strictness.STANDARD


def test_baseline_does_not_block_a_review_finding():
    result = assess_server(
        run(call_event(), findings=(finding(),)),
        policy=StrictnessPolicy(level=Strictness.BASELINE),
    )

    assert result.verdict is Verdict.FLAGGED
    assert result.blocked is False


def test_strict_blocks_an_unverified_run():
    result = assess_server(
        run(), policy=StrictnessPolicy(level=Strictness.STRICT)
    )

    assert result.verdict is Verdict.UNVERIFIED
    assert result.blocked is True


@pytest.mark.parametrize(
    ("cause", "expected"),
    [
        (RunCause.COST_CAPPED, UnverifiedCause.COST_CAPPED),
        (RunCause.STEP_LIMIT, UnverifiedCause.BUDGET_LIMIT),
        (RunCause.ACTION_LIMIT, UnverifiedCause.BUDGET_LIMIT),
        (RunCause.WALL_LIMIT, UnverifiedCause.BUDGET_LIMIT),
        (RunCause.MODEL_FAILED, UnverifiedCause.AGENT_FAILED),
        (RunCause.SANDBOX_UNAVAILABLE, UnverifiedCause.AGENT_FAILED),
        (RunCause.MISSING_KEY, UnverifiedCause.AGENT_FAILED),
    ],
)
def test_run_causes_map_to_the_conservative_unverified_causes(cause, expected):
    result = assess_server(run(call_event(), cause=cause))

    assert result.verdict is Verdict.UNVERIFIED
    assert result.cause is expected


def test_a_finding_with_a_run_failure_stays_unverified():
    result = assess_server(
        run(call_event(), findings=(finding(),), cause=RunCause.MODEL_FAILED)
    )

    assert result.verdict is Verdict.UNVERIFIED
    assert result.cause is UnverifiedCause.AGENT_FAILED
    assert result.findings == (finding(),)


def test_clean_and_malicious_are_refused():
    base = dict(
        server_name="demo",
        source_hash="b" * 64,
        task_hash="c" * 64,
        findings=(),
        strictness=Strictness.STANDARD,
        blocked=False,
    )
    with pytest.raises(VerdictError, match="server"):
        ServerAssessment(verdict=Verdict.CLEAN, cause=None, **base)
    with pytest.raises(VerdictError, match="server"):
        ServerAssessment(verdict=Verdict.MALICIOUS, cause=None, **base)


def test_the_payload_has_no_skill_or_trace_identity():
    result = assess_server(run(call_event()))

    payload = result.to_payload()

    assert payload["verdict"] == "unverified"
    assert payload["cause"] == "no-declared-scope"
    assert payload["server_name"] == "demo"
    assert payload["source_hash"] == "b" * 64
    assert payload["task_hash"] == hashlib.sha256(b"do the task").hexdigest()
    assert "skill_content_hash" not in payload
    assert "trace_hash" not in payload
