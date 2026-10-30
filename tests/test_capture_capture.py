import hashlib
from pathlib import Path

import pytest

from assay.agent import RunCause, RunOutcome, ToolAction, ToolCall, ToolResult, Usage
from assay.capture import EventKind, EventOutcome, capture
from assay.ingest import Scope, Skill
from assay.sandbox import DenialClass, DenialRecord, RunRecord


def skill(**over):
    base = dict(
        name="demo",
        description="does a demo",
        scope=Scope(),
        body="DEMO BODY\n",
        source_path=Path("demo/SKILL.md"),
        content_hash="a" * 64,
    )
    base.update(over)
    return Skill(**base)


def record(**over):
    base = dict(
        exit_code=0,
        signal=None,
        duration_s=0.0,
        stdout="ok",
        stderr="",
        truncated=False,
        denials=(),
        limit_exceeded=None,
        config_hash="f" * 64,
        run_root="/run",
        started_at="2026-10-29T00:00:00Z",
    )
    base.update(over)
    return RunRecord(**base)


def action(name, output="tool output", ok=True, record_=None, **arguments):
    return ToolAction(
        call=ToolCall(id=f"id-{name}", name=name, arguments=arguments),
        result=ToolResult(ok=ok, output=output, record=record_),
    )


def outcome(actions=(), **over):
    base = dict(
        cause=None,
        final_text="done",
        steps=1,
        actions=tuple(actions),
        usage=Usage(input_tokens=10, output_tokens=2),
        cost_usd=0.001,
    )
    base.update(over)
    return RunOutcome(**base)


def test_each_action_becomes_one_event_of_its_kind_in_order():
    actions = [
        action("read_file", path="in.txt", record_=record()),
        action("write_file", path="out.txt", content="x", record_=record()),
        action("http_get", url="https://example.com/", record_=record()),
        action("run_shell", command="echo hi", record_=record()),
        action("mystery_tool", record_=record()),
    ]
    trace = capture(skill(), "do it", outcome(actions))

    assert [event.kind for event in trace.events] == [
        EventKind.FILE_READ,
        EventKind.FILE_WRITE,
        EventKind.NETWORK,
        EventKind.SHELL,
        EventKind.TOOL,
        EventKind.INSTRUCTION,
        EventKind.INSTRUCTION,
    ]
    assert [event.target for event in trace.events[-2:]] == ["system", "user"]
    system, user = trace.events[-2:]
    assert system.content_sha256 == hashlib.sha256(b"DEMO BODY\n").hexdigest()
    assert user.content_sha256 == hashlib.sha256(b"do it").hexdigest()
    assert system.excerpt == "DEMO BODY\n"
    assert user.excerpt == "do it"


@pytest.mark.parametrize(
    "name, path, expected",
    [
        ("read_file", "./out/x.txt", "out/x.txt"),
        ("read_file", "out/x.txt", "out/x.txt"),
        ("read_file", "/run/out/x.txt", "out/x.txt"),
        ("read_file", "../escape.md", "../escape.md"),
        ("read_file", "/etc/passwd", "/etc/passwd"),
        ("write_file", "/run/out/deep/x.txt", "out/deep/x.txt"),
    ],
)
def test_file_targets_are_normalised(name, path, expected):
    trace = capture(
        skill(), "task", outcome([action(name, path=path, content="x", record_=record())])
    )
    assert trace.events[0].target == expected


def test_outcome_follows_the_run_record_and_carries_denials():
    denied = record(
        exit_code=1,
        denials=(DenialRecord(DenialClass.NETWORK, "blocked api.example.com"),),
    )
    trace = capture(
        skill(),
        "task",
        outcome(
            [
                action("read_file", path="a", record_=record()),
                action("http_get", url="https://example.com", record_=denied),
                action("run_shell", command="false", record_=record(exit_code=2)),
                action("read_file", path="missing.txt", ok=False, output="ENOENT"),
                action("read_file", path="b", record_=record(denials=denied.denials)),
            ]
        ),
    )

    assert [event.outcome for event in trace.events[:5]] == [
        EventOutcome.OK,
        EventOutcome.DENIED,
        EventOutcome.FAILED,
        EventOutcome.FAILED,
        EventOutcome.OK,
    ]
    assert trace.events[1].denials == ("network: blocked api.example.com",)
    assert trace.events[4].denials == ("network: blocked api.example.com",)
    assert trace.events[0].denials == ()
    assert trace.events[3].content_sha256 == hashlib.sha256(b"ENOENT").hexdigest()
    assert trace.events[3].excerpt == "ENOENT"


def test_trace_carries_skill_task_and_run_metadata():
    trace = capture(
        skill(name="demo"),
        "do it",
        outcome(
            cause=RunCause.STEP_LIMIT,
            usage=Usage(input_tokens=10, output_tokens=2),
            cost_usd=0.001,
        ),
    )

    assert trace.schema == 1
    assert trace.skill_name == "demo"
    assert trace.skill_content_hash == "a" * 64
    assert trace.task_sha256 == hashlib.sha256(b"do it").hexdigest()
    assert trace.cause == "step-limit"
    assert (trace.input_tokens, trace.output_tokens, trace.cost_usd) == (10, 2, 0.001)


def test_two_captures_of_identical_inputs_have_the_same_hash():
    actions = [action("read_file", path="a", record_=record())]
    first = capture(skill(), "task", outcome(actions))
    second = capture(skill(), "task", outcome(actions))
    assert first == second
    assert first.hash == second.hash


def test_excerpt_is_the_first_4096_bytes_and_valid_utf8():
    content = "aa" + "€" * 3000
    trace = capture(
        skill(),
        "task",
        outcome([action("read_file", path="a", record_=record(stdout=content))]),
    )
    event = trace.events[0]

    assert event.content_bytes == len(content.encode("utf-8"))
    assert event.content_sha256 == hashlib.sha256(content.encode("utf-8")).hexdigest()
    assert len(event.excerpt.encode("utf-8")) <= 4096
    assert event.excerpt == content.encode("utf-8")[:4096].decode("utf-8", "ignore")
    assert event.excerpt == "aa" + "€" * 1364


def test_empty_output_hashes_the_empty_bytes():
    trace = capture(
        skill(),
        "task",
        outcome([action("run_shell", command="true", record_=record(stdout="", stderr=""))]),
    )
    event = trace.events[0]

    assert event.content_bytes == 0
    assert event.excerpt == ""
    assert event.content_sha256 == hashlib.sha256(b"").hexdigest()


def test_write_file_hashes_the_model_payload_and_no_other_kind_does():
    payload = "héllo"
    trace = capture(
        skill(),
        "task",
        outcome(
            [
                action("write_file", path="a", content=payload, record_=record()),
                action("read_file", path="a", record_=record()),
                action("run_shell", command="echo", record_=record()),
            ]
        ),
    )

    assert trace.events[0].input_sha256 == hashlib.sha256(payload.encode("utf-8")).hexdigest()
    assert [event.input_sha256 for event in trace.events[1:]] == [None, None, None, None]


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://Example.COM/x?q=1", "example.com:443"),
        ("http://example.com", "example.com:80"),
        ("http://example.com:8080/x", "example.com:8080"),
        ("https://api.example.com:8443", "api.example.com:8443"),
        ("not a url", "not a url"),
        ("https://", "https://"),
    ],
)
def test_network_targets_are_a_lowercase_host_and_port(url, expected):
    trace = capture(skill(), "task", outcome([action("http_get", url=url, record_=record())]))
    assert trace.events[0].target == expected


def test_successful_stderr_and_truncation_are_kept():
    trace = capture(
        skill(),
        "task",
        outcome(
            [
                action(
                    "run_shell",
                    command="echo hi",
                    record_=record(stdout="out", stderr="err", truncated=True),
                )
            ]
        ),
    )
    event = trace.events[0]
    assert event.content_sha256 == hashlib.sha256(b"outerr").hexdigest()
    assert "err" in event.excerpt
    assert event.truncated is True


def test_instruction_events_appear_only_after_a_model_call():
    trace = capture(skill(), "task", outcome([], steps=0, cause=RunCause.MISSING_KEY))
    assert [event.kind for event in trace.events] == []


def test_a_write_without_content_has_no_input_hash_instead_of_an_empty_one():
    trace = capture(
        skill(),
        "task",
        outcome([action("write_file", path="x", ok=False, record_=record(exit_code=1))]),
    )
    assert trace.events[0].input_sha256 is None


def test_a_symlink_that_leaves_the_run_root_is_recorded_as_its_real_target(tmp_path):
    root = tmp_path / "run"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret").write_text("x")
    (root / "out").mkdir()
    (root / "out" / "link").symlink_to(outside / "secret")
    trace = capture(
        skill(),
        "task",
        outcome(
            [
                action(
                    "read_file",
                    path="out/link",
                    record_=record(run_root=str(root)),
                )
            ]
        ),
    )
    assert trace.events[0].target == (outside / "secret").as_posix()


def test_a_missing_path_or_url_does_not_crash_capture():
    trace = capture(
        skill(),
        "task",
        outcome(
            [
                action("read_file", record_=record()),
                action("http_get", record_=record()),
            ]
        ),
    )
    assert [event.target for event in trace.events[:2]] == ["invalid-path", "invalid-url"]
