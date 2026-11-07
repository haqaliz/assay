import hashlib
from pathlib import Path

from assay.capture import EventKind, EventOutcome, Trace
from assay.capture.diff import diff
from assay.ingest import Scope, Skill
from assay.mcp.client import MCPResult
from assay.mcp.events import event_for_call
from assay.verdict import UnverifiedCause, Verdict
from assay.verdict.assess import assess

SKILL_HASH = "a" * 64


def skill():
    return Skill(
        name="demo",
        description="does a demo",
        scope=Scope(files=(), network=(), tools=frozenset()),
        body="BODY\n",
        source_path=Path("SKILL.md"),
        content_hash=SKILL_HASH,
    )


def trace(*events):
    return Trace(
        skill_name="demo",
        skill_content_hash=SKILL_HASH,
        task_sha256="b" * 64,
        cause=None,
        input_tokens=0,
        output_tokens=0,
        cost_usd=0.0,
        events=tuple(events),
        sandbox_config_hashes=(),
    )


def test_event_for_call_maps_a_tool_call_to_tool_evidence():
    result = MCPResult(ok=True, text="hello")

    event = event_for_call("echo", {"text": "hi"}, result)

    assert event.kind is EventKind.TOOL
    assert event.outcome is EventOutcome.OK
    assert event.target == "echo"
    assert event.request == "tools/call"
    assert event.content_sha256 == hashlib.sha256(b"hello").hexdigest()
    assert event.content_bytes == 5
    assert event.excerpt == "hello"
    assert event.input_sha256 == hashlib.sha256(b'{"text":"hi"}').hexdigest()
    assert event.denials == ()
    assert event.truncated is False


def test_a_denial_makes_the_event_denied():
    result = MCPResult(ok=False, text="permission denied")

    event = event_for_call(
        "read_outside", {}, result, denials=("file-read /private/etc/hosts",)
    )

    assert event.outcome is EventOutcome.DENIED
    assert event.denials == ("file-read /private/etc/hosts",)


def test_a_failed_result_makes_the_event_failed():
    result = MCPResult(ok=False, text="boom")

    event = event_for_call("read_outside", {}, result)

    assert event.outcome is EventOutcome.FAILED


def test_long_content_is_truncated_for_the_excerpt_only():
    result = MCPResult(ok=True, text="x" * 5000)

    event = event_for_call("echo", {}, result)

    assert event.content_bytes == 5000
    assert event.content_sha256 == hashlib.sha256(b"x" * 5000).hexdigest()
    assert event.excerpt == "x" * 4096
    assert event.truncated is True


def test_tool_events_are_not_behavior():
    event = event_for_call("echo", {"text": "hi"}, MCPResult(ok=True, text="hi"))

    result = diff(skill(), trace(event))

    assert result.divergences == ()
    assert all(coverage.events == 0 for coverage in result.coverage)


def test_a_tool_only_trace_is_unverified_no_trigger():
    event = event_for_call("echo", {"text": "hi"}, MCPResult(ok=True, text="hi"))

    result = assess(skill(), trace(event))

    assert result.verdict is Verdict.UNVERIFIED
    assert result.cause is UnverifiedCause.NO_TRIGGER
    assert result.findings == ()
