import importlib
from pathlib import Path

import pytest

from assay.agent import ModelFailed, ModelPrice, ToolCall, Usage
from assay.agent.base import ModelReply
from assay.capture import TraceStore
from assay.cli import main
from assay.sandbox import RunRecord

cli_main = importlib.import_module("assay.cli.main")

PRICE = ModelPrice(input_per_mtok=2.0, output_per_mtok=1.0)
BASE = ["--max-cost", "1", "--model", "fake", "--input-price", "2", "--output-price", "1"]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in ("ASSAY_MODEL", "ASSAY_INPUT_PRICE", "ASSAY_OUTPUT_PRICE", "ASSAY_MAX_COST"):
        monkeypatch.delenv(name, raising=False)


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

    def complete(self, messages, tools):
        if self.error is not None:
            raise self.error
        return self.replies.pop(0)


class FakeSandbox:
    def __init__(self, stdout="file contents"):
        self.stdout = stdout
        self.configs = []

    def run(self, argv, config):
        self.configs.append(config)
        return RunRecord(
            exit_code=0,
            signal=None,
            duration_s=0.0,
            stdout=self.stdout,
            stderr="",
            truncated=False,
            denials=(),
            limit_exceeded=None,
            config_hash=config.config_hash,
            run_root=str(config.run_root),
            started_at="2026-10-29T00:00:00Z",
        )


def write_skill(tmp_path, files="[in.txt]", tools="Read"):
    path = tmp_path / "SKILL.md"
    path.write_text(
        "---\nname: demo\ndescription: Does a demo.\n"
        f"metadata:\n  assay:\n    files: {files}\n    network: []\n"
        f"allowed-tools: {tools}\n---\nBODY\n"
    )
    return path


def invoke(
    tmp_path,
    monkeypatch,
    model,
    sandbox=None,
    *,
    extra=(),
    root=None,
    skill=None,
):
    root = root if root is not None else tmp_path / "run"
    root.mkdir(exist_ok=True)
    monkeypatch.setattr(cli_main, "_make_run_root", lambda: root)
    out = tmp_path / "traces"
    argv = ["check", str(skill or write_skill(tmp_path)), *BASE, "--out", str(out), *extra]
    code = main(argv, model=model, sandbox=sandbox or FakeSandbox())
    return code, out, root


def saved_trace(out):
    paths = list(out.glob("*.json"))
    assert len(paths) == 1
    return TraceStore(out).load(paths[0]), paths[0]


def test_a_clean_run_exits_0_and_saves_its_trace(tmp_path, monkeypatch):
    model = FakeModel([reply("working", [call("read_file", path="in.txt")]), reply("done")])
    code, out, _ = invoke(tmp_path, monkeypatch, model)

    assert code == 0
    trace, path = saved_trace(out)
    assert trace.cause is None
    assert trace.skill_name == "demo"
    assert trace.input_tokens == 200
    assert trace.output_tokens == 20
    assert trace.cost_usd == pytest.approx(200 / 1e6 * 2.0 + 20 / 1e6 * 1.0)
    assert path.name == f"{trace.hash}.json"


def test_an_undeclared_read_is_flagged_and_exits_1(tmp_path, monkeypatch):
    model = FakeModel([reply("working", [call("read_file", path="secret.txt")]), reply("done")])
    code, out, _ = invoke(tmp_path, monkeypatch, model)

    assert code == 1
    trace, _ = saved_trace(out)
    assert trace.cause is None


def test_a_dangerous_shell_command_is_malicious_and_exits_1(tmp_path, monkeypatch):
    model = FakeModel(
        [reply("working", [call("run_shell", command="rm -rf /")]), reply("done")]
    )
    code, out, _ = invoke(tmp_path, monkeypatch, model, skill=write_skill(tmp_path, tools="Bash,Read"))

    assert code == 1
    trace, _ = saved_trace(out)
    assert [event.target for event in trace.events if event.kind == "shell"] == ["rm -rf /"]


def test_a_cost_capped_run_saves_the_trace_and_exits_1(tmp_path, monkeypatch):
    model = FakeModel([reply("thinking", usage=Usage(1_000_000, 0))])
    code, out, _ = invoke(tmp_path, monkeypatch, model)

    assert code == 1
    trace, _ = saved_trace(out)
    assert trace.cause == "cost-capped"
    assert trace.cost_usd == pytest.approx(2.0)


def test_a_model_failure_saves_the_trace_and_exits_1(tmp_path, monkeypatch):
    model = FakeModel([], error=ModelFailed("api down"))
    code, out, _ = invoke(tmp_path, monkeypatch, model)

    assert code == 1
    trace, _ = saved_trace(out)
    assert trace.cause == "model-failed"


def test_strictness_changes_only_blocking(tmp_path, monkeypatch):
    seen = []
    real_assess = cli_main.assess

    def spy(skill, trace, *, policy):
        assessment = real_assess(skill, trace, policy=policy)
        seen.append(assessment)
        return assessment

    monkeypatch.setattr(cli_main, "assess", spy)
    replies = lambda: [reply("working", [call("read_file", path="secret.txt")]), reply("done")]

    baseline, _, _ = invoke(tmp_path, monkeypatch, FakeModel(replies()), extra=("--strictness", "baseline"))
    standard, _, _ = invoke(tmp_path, monkeypatch, FakeModel(replies()), extra=("--strictness", "standard"))

    assert baseline == standard == 1
    assert seen[0].verdict is seen[1].verdict
    assert seen[0].blocked is False
    assert seen[1].blocked is True


def test_the_run_root_is_removed_unless_kept(tmp_path, monkeypatch, capsys):
    model = lambda: FakeModel([reply("working", [call("read_file", path="in.txt")]), reply("done")])
    code, _, root = invoke(tmp_path, monkeypatch, model())
    assert code == 0
    assert not root.exists()

    kept_root = tmp_path / "kept"
    code, _, kept = invoke(
        tmp_path, monkeypatch, model(), extra=("--keep-run-root",), root=kept_root
    )
    assert code == 0
    assert kept.exists()
    assert str(kept) in capsys.readouterr().out


def test_the_api_key_never_reaches_output_the_trace_or_a_jail_config(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-must-not-leak")
    sandbox = FakeSandbox()
    model = FakeModel([reply("working", [call("read_file", path="in.txt")]), reply("done")])
    code, out, _ = invoke(tmp_path, monkeypatch, model, sandbox=sandbox)

    captured = capsys.readouterr()
    trace_path = next(out.glob("*.json"))
    assert code == 0
    assert "sk-must-not-leak" not in captured.out + captured.err
    assert "sk-must-not-leak" not in trace_path.read_text()
    assert sandbox.configs
    for config in sandbox.configs:
        assert config.env == {}
        assert "sk-must-not-leak" not in repr(config)


def test_a_missing_key_is_one_line_and_exits_2_before_a_trace(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    out = tmp_path / "traces"
    code = main(
        ["check", str(write_skill(tmp_path)), *BASE, "--out", str(out)],
        sandbox=FakeSandbox(),
    )
    assert code == 2
    captured = capsys.readouterr()
    assert captured.err == "error: AgentUnavailable: ANTHROPIC_API_KEY is not set\n"
    assert "Traceback" not in captured.err
    assert not out.exists()
