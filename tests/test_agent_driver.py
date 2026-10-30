from pathlib import Path

import pytest

from assay.agent import (
    AgentUnavailable,
    Budget,
    ModelFailed,
    ModelPrice,
    RunCause,
    RunOutcome,
    ToolCall,
    ToolResult,
    Usage,
)
from assay.agent.base import Message, ModelReply
from assay.agent.driver import drive
from assay.agent.tools import TOOLS, Toolbox
from assay.ingest import Scope, Skill
from assay.sandbox import RunRecord, SandboxUnavailable

PRICE = ModelPrice(input_per_mtok=2.0, output_per_mtok=1.0)


def skill(**over):
    base = dict(
        name="demo",
        description="does a demo",
        scope=Scope(),
        body="DEMO BODY\n",
        source_path=Path("demo/SKILL.md"),
        content_hash="0" * 64,
    )
    base.update(over)
    return Skill(**base)


def reply(text, calls=(), usage=Usage(input_tokens=100, output_tokens=10)):
    return ModelReply(text=text, tool_calls=tuple(calls), usage=usage)


def call(name, **arguments):
    return ToolCall(id=f"id-{name}", name=name, arguments=arguments)


class FakeModel:
    max_tokens = 1024

    def __init__(self, replies, price=PRICE, error=None):
        self.price = price
        self.replies = list(replies)
        self.error = error
        self.seen = []

    def complete(self, messages, tools):
        self.seen.append((list(messages), list(tools)))
        if self.error is not None:
            raise self.error
        return self.replies.pop(0)


class FakeToolbox:
    def __init__(self, results=()):
        self.calls = []
        self.results = list(results)

    def execute(self, tool_call):
        self.calls.append(tool_call)
        if self.results:
            return self.results.pop(0)
        return ToolResult(ok=True, output=f"{tool_call.name}-ok")


def test_three_turns_execute_every_action_in_order_and_finish():
    first, second = call("read_file", path="a.txt"), call("write_file", path="b.txt", content="b")
    model = FakeModel([reply("thinking", [first]), reply("thinking", [second]), reply("all done")])
    toolbox = FakeToolbox([ToolResult(True, "a-data"), ToolResult(True, "b-written")])

    outcome = drive(skill(), "do it", model, toolbox, Budget(max_usd=1.0))

    assert isinstance(outcome, RunOutcome)
    assert outcome.cause is None
    assert outcome.final_text == "all done"
    assert outcome.finished
    assert outcome.steps == 3
    assert [action.call for action in outcome.actions] == [first, second]
    assert [action.result.output for action in outcome.actions] == ["a-data", "b-written"]
    assert outcome.usage == Usage(input_tokens=300, output_tokens=30)
    assert outcome.cost_usd == pytest.approx(300 / 1e6 * 2.0 + 30 / 1e6 * 1.0)
    assert toolbox.calls == [first, second]


def test_driver_sends_the_skill_body_the_task_and_all_four_tools_every_turn():
    model = FakeModel([reply("done")])
    drive(skill(), "TASK TEXT", model, FakeToolbox(), Budget(max_usd=1.0))
    messages, tools = model.seen[0]
    assert messages[0] == Message("system", "DEMO BODY\n")
    assert messages[1] == Message("user", "TASK TEXT")
    assert tools == list(TOOLS)


def test_declared_scope_never_filters_the_tools():
    model = FakeModel([reply("done")])
    scoped = skill(scope=Scope(tools=frozenset(), files=(), network=()))
    drive(scoped, "task", model, FakeToolbox(), Budget(max_usd=1.0))
    assert model.seen[0][1] == list(TOOLS)


def test_tool_result_and_assistant_turn_are_appended_for_the_next_call():
    model = FakeModel([reply("working", [call("read_file", path="a")]), reply("done")])
    toolbox = FakeToolbox([ToolResult(False, "")])
    drive(skill(), "task", model, toolbox, Budget(max_usd=1.0))
    messages = model.seen[1][0]
    assert messages[2].role == "assistant"
    assert messages[2].content == "working"
    assert messages[2].tool_calls == (call("read_file", path="a"),)
    assert messages[3].role == "tool"
    assert messages[3].tool_call_id == "id-read_file"
    assert messages[3].content == "tool 'read_file' failed"


def test_cost_cap_stops_before_the_next_call_and_keeps_the_overshoot_to_one_reply():
    expensive = reply("working", [call("run_shell", command="true")], Usage(1_000_000, 0))
    model = FakeModel([expensive, expensive])
    toolbox = FakeToolbox()
    outcome = drive(skill(), "task", model, toolbox, Budget(max_usd=2.5))
    assert outcome.cause is RunCause.COST_CAPPED
    assert outcome.steps == 2
    assert outcome.finished is False
    assert outcome.cost_usd == pytest.approx(4.0)
    assert outcome.cost_usd - 2.5 <= 2.0
    assert len(toolbox.calls) == 1


def test_cost_cap_at_exact_budget_prevents_another_call():
    model = FakeModel([reply("working", [call("read_file", path="a")], Usage(1_000_000, 0))])
    outcome = drive(skill(), "task", model, FakeToolbox(), Budget(max_usd=2.0))
    assert outcome.cause is RunCause.COST_CAPPED
    assert outcome.steps == 1


def test_step_limit_returns_the_transcript_so_far():
    looping = reply("again", [call("run_shell", command="true")])
    model = FakeModel([looping, looping, looping, looping])
    toolbox = FakeToolbox()
    outcome = drive(skill(), "task", model, toolbox, Budget(max_usd=100.0, max_steps=2))
    assert outcome.cause is RunCause.STEP_LIMIT
    assert outcome.steps == 2
    assert len(outcome.actions) == 2
    assert len(model.seen) == 2


def test_wall_limit_is_checked_before_each_call_with_an_injected_clock():
    times = iter([0.0, 0.0, 50.0])
    model = FakeModel([reply("working", [call("run_shell", command="true")])])
    outcome = drive(
        skill(),
        "task",
        model,
        FakeToolbox(),
        Budget(max_usd=10.0, max_wall_seconds=10.0),
        clock=lambda: next(times),
    )
    assert outcome.cause is RunCause.WALL_LIMIT
    assert outcome.steps == 1
    assert len(model.seen) == 1


def test_model_failure_becomes_a_named_cause_and_keeps_prior_actions():
    model = FakeModel([])
    toolbox = FakeToolbox([ToolResult(True, "data")])

    def complete(messages, tools):
        model.seen.append((list(messages), list(tools)))
        if len(model.seen) == 2:
            raise ModelFailed("api down")
        return reply("working", [call("read_file", path="a")])

    model.complete = complete
    outcome = drive(skill(), "task", model, toolbox, Budget(max_usd=10.0))
    assert outcome.cause is RunCause.MODEL_FAILED
    assert outcome.steps == 1
    assert len(outcome.actions) == 1
    assert outcome.final_text is None


def test_other_agent_errors_propagate_but_a_lost_sandbox_is_a_named_cause():
    model = FakeModel([])
    model.error = AgentUnavailable("no key", cause=RunCause.MISSING_KEY)
    with pytest.raises(AgentUnavailable):
        drive(skill(), "task", model, FakeToolbox(), Budget(max_usd=1.0))

    class BrokenToolbox:
        def execute(self, tool_call):
            raise SandboxUnavailable("cannot confine")

    model = FakeModel([reply("working", [call("read_file", path="a")])])
    outcome = drive(skill(), "task", model, BrokenToolbox(), Budget(max_usd=1.0))
    assert outcome.cause is RunCause.SANDBOX_UNAVAILABLE
    assert outcome.steps == 1
    assert outcome.actions == ()


def test_pre_call_estimate_stops_before_an_unaffordable_call():
    class BigOutput(FakeModel):
        max_tokens = 1_000_000

    model = BigOutput([reply("never")], price=ModelPrice(input_per_mtok=0.0, output_per_mtok=1.0))
    outcome = drive(skill(), "task", model, FakeToolbox(), Budget(max_usd=0.5))
    assert outcome.cause is RunCause.COST_CAPPED
    assert outcome.steps == 0
    assert model.seen == []
    assert outcome.cost_usd == 0.0


def test_action_limit_bounds_a_single_reply_with_many_tool_calls():
    calls = [call("run_shell", command=f"echo {i}") for i in range(6)]
    model = FakeModel([reply("many", calls)])
    toolbox = FakeToolbox()
    outcome = drive(
        skill(), "task", model, toolbox, Budget(max_usd=10.0, max_actions=3)
    )
    assert outcome.cause is RunCause.ACTION_LIMIT
    assert len(outcome.actions) == 3
    assert len(toolbox.calls) == 3


def test_tool_output_sent_back_to_the_model_is_truncated():
    from assay.agent.driver import MAX_TOOL_CONTENT_CHARS

    model = FakeModel([reply("working", [call("read_file", path="a")]), reply("done")])
    toolbox = FakeToolbox([ToolResult(True, "x" * (MAX_TOOL_CONTENT_CHARS + 500))])
    drive(skill(), "task", model, toolbox, Budget(max_usd=1.0))
    tool_message = model.seen[1][0][3]
    assert tool_message.role == "tool"
    assert len(tool_message.content) < MAX_TOOL_CONTENT_CHARS + 100
    assert tool_message.content.endswith("...[truncated]")


def test_empty_text_without_tool_calls_finishes_with_empty_string():
    outcome = drive(
        skill(), "task", FakeModel([reply(None)]), FakeToolbox(), Budget(max_usd=1.0)
    )
    assert outcome.cause is None
    assert outcome.final_text == ""
    assert outcome.finished


class FakeSandbox:
    def __init__(self):
        self.configs = []

    def run(self, argv, config):
        self.configs.append(config)
        return RunRecord(
            exit_code=0,
            signal=None,
            duration_s=0.0,
            stdout="ok",
            stderr="",
            truncated=False,
            denials=(),
            limit_exceeded=None,
            config_hash=config.config_hash,
            run_root=str(config.run_root),
            started_at="2026-10-29T00:00:00Z",
        )


def test_no_model_credential_reaches_any_sandbox_config_during_a_run(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-must-not-leak")
    sandbox = FakeSandbox()
    toolbox = Toolbox(sandbox, tmp_path)
    calls = [
        call("read_file", path="a.txt"),
        call("write_file", path="b.txt", content="x"),
        call("run_shell", command="true"),
        call("http_get", url="https://203.0.113.10"),
    ]
    model = FakeModel([reply("working", calls), reply("done")])
    outcome = drive(skill(), "task", model, toolbox, Budget(max_usd=1.0))

    assert outcome.cause is None
    assert len(sandbox.configs) == 4
    for config in sandbox.configs:
        assert config.env == {}
        assert "ANTHROPIC_API_KEY" not in config.env
        assert all("sk-must-not-leak" not in str(value) for value in config.env.values())
        assert config.run_root == toolbox.run_root


def test_outcome_carries_no_verdict_words():
    outcome = drive(skill(), "task", FakeModel([reply("done")]), FakeToolbox(), Budget(max_usd=1.0))
    rendered = repr(outcome).upper()
    for word in ("CLEAN", "FLAGGED", "MALICIOUS"):
        assert word not in rendered


def test_a_jail_failure_mid_run_is_a_named_cause_not_a_tool_error():
    from assay.sandbox import SandboxFailed

    class BrokenToolbox:
        def execute(self, tool_call):
            raise SandboxFailed("no jail")

    model = FakeModel([reply("working", [call("read_file", path="a")])])
    outcome = drive(skill(), "task", model, BrokenToolbox(), Budget(max_usd=1.0))
    assert outcome.cause is RunCause.SANDBOX_UNAVAILABLE
    assert outcome.actions == ()
