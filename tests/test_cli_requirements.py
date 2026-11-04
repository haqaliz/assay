import importlib
import json
import sys
from pathlib import Path

import pytest

from assay.agent import ModelPrice, ToolCall, Usage
from assay.agent.base import ModelReply
from assay.cli import main
from assay.cli.requirements import unmet_requirements
from assay.ingest import Format, Scope, Skill
from assay.sandbox import DEFAULT_PATH, RunRecord

cli_main = importlib.import_module("assay.cli.main")

PRICE = ModelPrice(input_per_mtok=2.0, output_per_mtok=1.0)
BASE = ["--max-cost", "1", "--model", "fake", "--input-price", "2", "--output-price", "1"]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in ("ASSAY_MODEL", "ASSAY_INPUT_PRICE", "ASSAY_OUTPUT_PRICE", "ASSAY_MAX_COST"):
        monkeypatch.delenv(name, raising=False)


def skill(*requirements):
    return Skill(
        name="gemini",
        description="Generate images with the Gemini CLI.",
        scope=Scope(),
        body="BODY\n",
        source_path=Path("gemini/SKILL.md"),
        content_hash="a" * 64,
        format=Format.OPENCLAW,
        requirements=requirements,
    )


def probe(resolved=()):
    calls = []

    def which(name, path):
        calls.append((name, path))
        return f"/usr/bin/{name}" if name in resolved else None

    return which, calls


@pytest.mark.parametrize(
    ("requirements", "resolved", "platform", "expected"),
    [
        (("env:GEMINI_API_KEY",), (), "darwin", ("env:GEMINI_API_KEY",)),
        (("config:browser.enabled",), (), "darwin", ("config:browser.enabled",)),
        (("bin:ls",), ("ls",), "darwin", ()),
        (("bin:missing",), ("ls",), "darwin", ("bin:missing",)),
        (("any-bin:rg,grep",), ("rg", "grep"), "darwin", ()),
        (("any-bin:rg,grep",), ("grep",), "darwin", ()),
        (("any-bin:rg,grep",), (), "darwin", ("any-bin:rg,grep",)),
        (("os:darwin",), (), "darwin", ()),
        (("os:macos",), (), "darwin", ()),
        (("os:linux",), (), "darwin", ("os:linux",)),
        (("os:linux,macos",), (), "darwin", ()),
        (("os:darwin,linux",), (), "linux", ()),
        (
            ("env:A", "bin:ls", "config:x", "os:linux"),
            ("ls",),
            "darwin",
            ("env:A", "config:x", "os:linux"),
        ),
        ((), (), "darwin", ()),
    ],
)
def test_unmet_requirements_table(requirements, resolved, platform, expected):
    which, _ = probe(resolved)

    assert (
        unmet_requirements(
            skill(*requirements), which=which, platform=platform
        )
        == expected
    )


def test_which_uses_the_jail_path_by_default():
    which, calls = probe({"ls"})

    assert unmet_requirements(skill("bin:ls"), which=which) == ()
    assert calls == [("ls", DEFAULT_PATH)]


def test_a_custom_path_reaches_which():
    which, calls = probe({"ls"})

    assert unmet_requirements(skill("bin:ls"), which=which, path="/custom") == ()
    assert calls == [("ls", "/custom")]


def test_the_default_which_searches_the_jail_path():
    assert unmet_requirements(skill("bin:ls")) == ()
    assert unmet_requirements(skill("bin:assay-no-such-binary")) == (
        "bin:assay-no-such-binary",
    )


def test_default_path_has_one_source_and_stays_importable_from_seatbelt():
    from assay.sandbox import seatbelt
    from assay.sandbox.config import DEFAULT_PATH as CONFIG_PATH

    assert DEFAULT_PATH == CONFIG_PATH == seatbelt.DEFAULT_PATH
    assert DEFAULT_PATH == "/usr/bin:/bin:/usr/sbin:/sbin"


class SentinelModel:
    max_tokens = 1024

    def __init__(self):
        self.price = PRICE
        self.calls = 0

    def complete(self, messages, tools):
        self.calls += 1
        raise AssertionError("the model must not be called")


class SentinelSandbox:
    def __init__(self):
        self.calls = 0

    def run(self, argv, config):
        self.calls += 1
        raise AssertionError("the sandbox must not be called")


def write_openclaw_skill(tmp_path, *, requires=None, os_list=None):
    lines = ["---\nname: gemini\ndescription: Generate images.\nmetadata:\n  openclaw:\n"]
    if requires is not None:
        lines.append("    requires:\n")
        lines.extend(f"      {key}: {value}\n" for key, value in requires.items())
    if os_list is not None:
        lines.append(f"    os: {os_list}\n")
    lines.append("---\nBODY\n")
    path = tmp_path / "SKILL.md"
    path.write_text("".join(lines))
    return path


def refuse(tmp_path, capsys, path, *, as_json=False):
    model, sandbox = SentinelModel(), SentinelSandbox()
    out = tmp_path / "traces"
    argv = ["check", str(path), *BASE, "--out", str(out)]
    if as_json:
        argv.append("--json")
    code = main(argv, model=model, sandbox=sandbox)
    captured = capsys.readouterr()
    assert code == 1
    assert model.calls == 0
    assert sandbox.calls == 0
    assert not out.exists()
    return captured


def test_check_refuses_an_openclaw_skill_with_an_env_requirement_before_any_model_call(
    tmp_path, capsys
):
    path = write_openclaw_skill(tmp_path, requires={"env": "[GEMINI_API_KEY]"})

    captured = refuse(tmp_path, capsys, path)

    assert "REQUIREMENTS_UNMET" in captured.out
    assert "env:GEMINI_API_KEY" in captured.out
    assert captured.err == ""


def test_check_refuses_a_config_requirement(tmp_path, capsys):
    path = write_openclaw_skill(tmp_path, requires={"config": "[browser.enabled]"})

    captured = refuse(tmp_path, capsys, path)

    assert "REQUIREMENTS_UNMET" in captured.out
    assert "detail: the sandbox cannot satisfy: config:browser.enabled\n" in captured.out


def test_check_refuses_a_missing_bin(tmp_path, capsys):
    path = write_openclaw_skill(tmp_path, requires={"bins": "[assay-no-such-binary]"})

    captured = refuse(tmp_path, capsys, path)

    assert "REQUIREMENTS_UNMET" in captured.out
    assert "detail: the sandbox cannot satisfy: bin:assay-no-such-binary\n" in captured.out


@pytest.mark.skipif(sys.platform == "linux", reason="linux is the host platform")
def test_check_refuses_a_mismatched_os(tmp_path, capsys):
    path = write_openclaw_skill(tmp_path, os_list="[linux]")

    captured = refuse(tmp_path, capsys, path)

    assert "REQUIREMENTS_UNMET" in captured.out
    assert "detail: the sandbox cannot satisfy: os:linux\n" in captured.out


def test_requirements_refusal_json_uses_the_existing_envelope(tmp_path, capsys):
    path = write_openclaw_skill(tmp_path, requires={"env": "[GEMINI_API_KEY]"})

    captured = refuse(tmp_path, capsys, path, as_json=True)

    assert json.loads(captured.out) == {
        "schema": 1,
        "skill": {"path": str(path)},
        "verdict": "unverified",
        "cause": "requirements-unmet",
        "detail": "the sandbox cannot satisfy: env:GEMINI_API_KEY",
    }
    assert captured.out.count("\n") == 1


class FakeModel:
    max_tokens = 1024

    def __init__(self, replies):
        self.price = PRICE
        self.replies = list(replies)
        self.calls = 0

    def complete(self, messages, tools):
        self.calls += 1
        return self.replies.pop(0)


class FakeSandbox:
    def __init__(self):
        self.calls = 0

    def run(self, argv, config):
        self.calls += 1
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


def test_check_runs_when_requirements_are_met(tmp_path, monkeypatch, capsys):
    path = write_openclaw_skill(tmp_path, requires={"bins": "[ls]"})
    root = tmp_path / "run"
    root.mkdir()
    monkeypatch.setattr(cli_main, "_make_run_root", lambda: root)
    model = FakeModel(
        [
            ModelReply(
                text="working",
                tool_calls=(
                    ToolCall(id="id-read", name="read_file", arguments={"path": "in.txt"}),
                ),
                usage=Usage(100, 10),
            ),
            ModelReply(text="done", tool_calls=(), usage=Usage(100, 10)),
        ]
    )
    sandbox = FakeSandbox()
    out = tmp_path / "traces"

    code = main(
        ["check", str(path), *BASE, "--out", str(out)], model=model, sandbox=sandbox
    )

    report = capsys.readouterr().out
    assert model.calls == 2
    assert sandbox.calls == 1
    assert "format: openclaw\n" in report
    assert "requirements: bin:ls\n" in report
    assert len(list(out.glob("*.json"))) == 1
    assert code == 1
