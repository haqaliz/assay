import importlib
import json
from pathlib import Path

import pytest

from assay.agent import ModelPrice, ToolCall, Usage
from assay.agent.base import ModelReply
from assay.capture import EventOutcome, Trace
from assay.cli import main
from assay.cli.output import render_human, render_json
from assay.ingest import Scope, Skill
from assay.sandbox import RunRecord
from assay.verdict import (
    Assessment,
    Finding,
    FindingClass,
    Severity,
    Strictness,
    UnverifiedCause,
    Verdict,
)

cli_main = importlib.import_module("assay.cli.main")

PRICE = ModelPrice(input_per_mtok=2.0, output_per_mtok=1.0)
BASE = ["--max-cost", "1", "--model", "fake", "--input-price", "2", "--output-price", "1"]
TRACE_PATH = Path("/abs/traces/abc.json")


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in ("ASSAY_MODEL", "ASSAY_INPUT_PRICE", "ASSAY_OUTPUT_PRICE", "ASSAY_MAX_COST"):
        monkeypatch.delenv(name, raising=False)


def skill():
    return Skill(
        name="demo",
        description="Does a demo.",
        scope=Scope(tools=frozenset({"Read"}), files=("in.txt",), network=()),
        body="BODY\n",
        source_path=Path("demo/SKILL.md"),
        content_hash="a" * 64,
    )


def trace():
    return Trace(
        skill_name="demo",
        skill_content_hash="a" * 64,
        task_sha256="c" * 64,
        cause=None,
        input_tokens=10,
        output_tokens=2,
        cost_usd=0.001,
        events=(),
    )


def assessment(verdict=Verdict.CLEAN, findings=(), cause=None, blocked=False, strictness=Strictness.STANDARD):
    return Assessment(
        verdict=verdict,
        findings=findings,
        cause=cause,
        blocked=blocked,
        strictness=strictness,
        skill_content_hash="a" * 64,
        trace_hash="b" * 64,
    )


def test_human_report_has_one_line_per_field_and_finding():
    finding = Finding(
        class_=FindingClass.UNDECLARED_FILE,
        severity=Severity.REVIEW,
        target="secret.txt",
        reason="no declared file pattern matches 'secret.txt'",
        outcome=EventOutcome.OK,
    )
    report = render_human(
        skill(),
        assessment(Verdict.FLAGGED, (finding,), blocked=True),
        TRACE_PATH,
        trace(),
        1,
    )
    assert report == (
        "skill: demo aaaaaaaaaaaa\n"
        "verdict: FLAGGED\n"
        "cause: -\n"
        "strictness: standard (blocked: yes)\n"
        "findings:\n"
        "[REVIEW] undeclared-file secret.txt: no declared file pattern matches 'secret.txt'\n"
        f"trace: {TRACE_PATH}\n"
        "cost: $0.0010 (10 input, 2 output tokens)\n"
        "exit: 1\n"
    )


def test_human_report_names_an_unverified_cause_and_no_findings():
    report = render_human(
        skill(),
        assessment(Verdict.UNVERIFIED, cause=UnverifiedCause.COST_CAPPED, blocked=True),
        TRACE_PATH,
        trace(),
        1,
    )
    assert "verdict: UNVERIFIED\n" in report
    assert "cause: COST_CAPPED\n" in report
    assert "findings: none\n" in report


def test_json_report_is_one_canonical_line_with_the_exact_field_set():
    report = render_json(skill(), assessment(), TRACE_PATH, trace())
    assert report == (
        '{"blocked":false,"cause":null,"cost_usd":0.001,"findings":[],"schema":1,'
        '"skill":{"content_hash":"' + "a" * 64 + '","name":"demo","path":"demo/SKILL.md"},'
        '"strictness":"standard","trace":"/abs/traces/abc.json",'
        '"trace_hash":"' + "b" * 64 + '",'
        '"usage":{"input_tokens":10,"output_tokens":2},"verdict":"clean"}\n'
    )


def test_json_report_carries_finding_fields():
    finding = Finding(
        class_=FindingClass.SHELL,
        severity=Severity.HIGH,
        target="rm -rf /",
        reason="dangerous shell pattern 'rm -rf /'",
        outcome=EventOutcome.DENIED,
        review_required=True,
    )
    payload = json.loads(
        render_json(
            skill(), assessment(Verdict.MALICIOUS, (finding,), blocked=True), TRACE_PATH, trace()
        )
    )
    assert payload["findings"] == [
        {
            "class": "shell",
            "severity": "high",
            "target": "rm -rf /",
            "reason": "dangerous shell pattern 'rm -rf /'",
            "outcome": "denied",
            "review_required": True,
        }
    ]


class FakeModel:
    max_tokens = 1024

    def __init__(self, replies):
        self.price = PRICE
        self.replies = list(replies)

    def complete(self, messages, tools):
        return self.replies.pop(0)


class FakeSandbox:
    def run(self, argv, config):
        return RunRecord(
            exit_code=0,
            signal=None,
            duration_s=0.0,
            stdout="file contents",
            stderr="",
            truncated=False,
            denials=(),
            limit_exceeded=None,
            config_hash=config.config_hash,
            run_root=str(config.run_root),
            started_at="2026-10-29T00:00:00Z",
        )


def reply(text, calls=()):
    return ModelReply(text=text, tool_calls=tuple(calls), usage=Usage(100, 10))


def call(name, **arguments):
    return ToolCall(id=f"id-{name}", name=name, arguments=arguments)


def write_skill(directory):
    path = Path(directory) / "SKILL.md"
    path.write_text(
        "---\nname: demo\ndescription: Does a demo.\n"
        "metadata:\n  assay:\n    files: [in.txt]\n    network: []\n"
        "allowed-tools: Read\n---\nBODY\n"
    )
    return path


def model():
    return FakeModel([reply("working", [call("read_file", path="in.txt")]), reply("done")])


def test_the_default_out_is_the_invocation_directorys_dot_assay(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    root = tmp_path / "run"
    root.mkdir()
    monkeypatch.setattr(cli_main, "_make_run_root", lambda: root)
    code = main(
        ["check", str(write_skill(tmp_path)), *BASE], model=model(), sandbox=FakeSandbox()
    )
    out = capsys.readouterr().out
    traces = list((tmp_path / ".assay" / "traces").glob("*.json"))
    assert code == 0
    assert len(traces) == 1
    assert f"trace: {traces[0].resolve()}\n" in out


def test_an_out_override_is_created_and_the_trace_is_absolute(tmp_path, monkeypatch, capsys):
    root = tmp_path / "run"
    root.mkdir()
    monkeypatch.setattr(cli_main, "_make_run_root", lambda: root)
    out = tmp_path / "nested" / "traces"
    code = main(
        ["check", str(write_skill(tmp_path)), *BASE, "--out", str(out)],
        model=model(),
        sandbox=FakeSandbox(),
    )
    report = capsys.readouterr().out
    trace_path = next(out.glob("*.json"))
    assert code == 0
    assert trace_path.is_absolute()
    assert f"trace: {trace_path.resolve()}\n" in report


def test_two_identical_runs_produce_identical_stdout(tmp_path, monkeypatch, capsys):
    root = tmp_path / "run"

    def fresh_root():
        root.mkdir(exist_ok=True)
        return root

    monkeypatch.setattr(cli_main, "_make_run_root", fresh_root)
    argv = ["check", str(write_skill(tmp_path)), *BASE, "--json", "--out", str(tmp_path / "t")]

    assert main(argv, model=model(), sandbox=FakeSandbox()) == 0
    first = capsys.readouterr().out
    assert main(argv, model=model(), sandbox=FakeSandbox()) == 0
    second = capsys.readouterr().out

    assert first == second
    assert first.count("\n") == 1


def test_json_run_reports_the_assessment_and_absolute_trace(tmp_path, monkeypatch, capsys):
    root = tmp_path / "run"
    root.mkdir()
    monkeypatch.setattr(cli_main, "_make_run_root", lambda: root)
    out = tmp_path / "traces"
    code = main(
        ["check", str(write_skill(tmp_path)), *BASE, "--json", "--out", str(out)],
        model=model(),
        sandbox=FakeSandbox(),
    )
    payload = json.loads(capsys.readouterr().out)
    trace_path = next(out.glob("*.json"))
    assert code == 0
    assert set(payload) == {
        "schema",
        "skill",
        "verdict",
        "cause",
        "blocked",
        "strictness",
        "findings",
        "trace",
        "trace_hash",
        "usage",
        "cost_usd",
    }
    assert payload["verdict"] == "clean"
    assert payload["cause"] is None
    assert payload["blocked"] is False
    assert payload["skill"]["name"] == "demo"
    assert payload["trace"] == str(trace_path.resolve())
    assert payload["trace_hash"] == trace_path.stem
    assert payload["usage"] == {"input_tokens": 200, "output_tokens": 20}


def test_an_out_symlink_is_a_one_line_environment_error(tmp_path, monkeypatch, capsys):
    root = tmp_path / "run"
    root.mkdir()
    monkeypatch.setattr(cli_main, "_make_run_root", lambda: root)
    real = tmp_path / "real"
    real.mkdir()
    linked = tmp_path / "linked"
    linked.symlink_to(real, target_is_directory=True)
    code = main(
        ["check", str(write_skill(tmp_path)), *BASE, "--out", str(linked)],
        model=model(),
        sandbox=FakeSandbox(),
    )
    err = capsys.readouterr().err
    assert code == 2
    assert err.startswith("error: CaptureError: trace root must not be a symlink")
    assert err.count("\n") == 1


def test_a_skill_name_cannot_inject_a_second_verdict_line():
    hostile = skill()
    object.__setattr__(hostile, "name", "x\nverdict: CLEAN")
    report = render_human(
        hostile,
        assessment(Verdict.UNVERIFIED, cause=UnverifiedCause.NO_TRIGGER),
        TRACE_PATH,
        trace(),
        1,
    )
    assert [line for line in report.splitlines() if line.startswith("verdict:")] == [
        "verdict: UNVERIFIED"
    ]
    assert "x\\x0averdict: CLEAN" in report


def test_non_ascii_text_is_preserved_in_the_human_report():
    named = skill()
    object.__setattr__(named, "name", "café")
    report = render_human(
        named, assessment(Verdict.CLEAN), TRACE_PATH, trace(), 0
    )
    assert "skill: café " in report
