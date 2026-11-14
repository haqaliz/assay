import importlib
import json
import shutil
import subprocess

import pytest

from assay.agent import ModelPrice, ToolCall, Usage
from assay.agent.base import ModelReply
from assay.cli import main
from assay.sandbox import RunRecord

cli_main = importlib.import_module("assay.cli.main")

PRICE = ModelPrice(input_per_mtok=2.0, output_per_mtok=1.0)
BASE = ["--max-cost", "1", "--model", "fake", "--input-price", "2", "--output-price", "1"]

requires_ssh_keygen = pytest.mark.skipif(
    shutil.which("ssh-keygen") is None, reason="ssh-keygen not installed"
)

RULE = (
    "---\n"
    "description: Writes one report.\n"
    'globs: ["reports/*.md"]\n'
    "---\n"
    "Write reports/out.md.\n"
)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in ("ASSAY_MODEL", "ASSAY_INPUT_PRICE", "ASSAY_OUTPUT_PRICE", "ASSAY_MAX_COST"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture(scope="module")
def keypair(tmp_path_factory):
    private_key = tmp_path_factory.mktemp("keys") / "key"
    subprocess.run(
        [
            "ssh-keygen",
            "-q",
            "-t",
            "ed25519",
            "-N",
            "",
            "-C",
            "assay-cursor-e2e-test",
            "-f",
            str(private_key),
        ],
        check=True,
        capture_output=True,
    )
    return private_key, private_key.with_suffix(".pub")


def reply(text, calls=()):
    return ModelReply(text=text, tool_calls=tuple(calls), usage=Usage(100, 10))


def call(name, **arguments):
    return ToolCall(id=f"id-{name}", name=name, arguments=arguments)


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


def check_rule(tmp_path, monkeypatch):
    root = tmp_path / "run"
    root.mkdir(exist_ok=True)
    monkeypatch.setattr(cli_main, "_make_run_root", lambda: root)
    out = tmp_path / "traces"
    rule_path = tmp_path / "reports.mdc"
    rule_path.write_text(RULE, encoding="utf-8")
    model = FakeModel(
        [
            reply(
                "working",
                [call("write_file", path="reports/out.md", content="hello")],
            ),
            reply("done"),
        ]
    )
    code = main(
        ["check", str(rule_path), *BASE, "--out", str(out)],
        model=model,
        sandbox=FakeSandbox(),
    )
    return code, rule_path, next(out.glob("*.json"))


def bundle_path_for(trace_path):
    return trace_path.parent / f"{trace_path.stem}.bundle.json"


def test_check_reports_cursor_format_and_saves_the_trace(tmp_path, monkeypatch, capsys):
    code, _, trace_path = check_rule(tmp_path, monkeypatch)

    report = capsys.readouterr().out
    assert code == 1
    assert "format: cursor\n" in report
    assert "requirements: none\n" in report
    assert "verdict: UNVERIFIED\n" in report
    assert f"trace: {trace_path.resolve()}\n" in report
    assert trace_path.is_file()


@requires_ssh_keygen
def test_a_cursor_rule_bundles_and_verifies(tmp_path, monkeypatch, keypair, capsys):
    private_key, public_key = keypair
    _, rule_path, trace_path = check_rule(tmp_path, monkeypatch)
    capsys.readouterr()

    code = main(
        ["bundle", str(trace_path), "--skill", str(rule_path), "--key", str(private_key)]
    )

    assert code == 0
    bundle_path = bundle_path_for(trace_path)
    payload = json.loads(bundle_path.read_text(encoding="utf-8"))
    assert payload["schema"] == 3
    assert payload["skill"]["format"] == "cursor"
    capsys.readouterr()

    code = main(["verify", str(bundle_path), "--public-key", str(public_key)])

    report = capsys.readouterr().out
    assert code == 0
    assert "signature: verified\n" in report
    assert "replay: verified\n" in report
