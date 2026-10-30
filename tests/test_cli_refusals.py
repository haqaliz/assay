import importlib
import json
from pathlib import Path

import pytest

from assay.cli import main
from assay.ingest import SkillParseError, parse_skill
from assay.sandbox import SandboxUnavailable

cli_main = importlib.import_module("assay.cli.main")

REQUIRED = [
    "--max-cost",
    "1",
    "--model",
    "m",
    "--input-price",
    "2",
    "--output-price",
    "3",
]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in ("ASSAY_MODEL", "ASSAY_INPUT_PRICE", "ASSAY_OUTPUT_PRICE", "ASSAY_MAX_COST"):
        monkeypatch.delenv(name, raising=False)


def valid_skill(tmp_path):
    path = tmp_path / "SKILL.md"
    path.write_text(
        "---\nname: demo\ndescription: does a demo\n"
        "metadata:\n  assay:\n    files: [in.txt]\n    network: []\n"
        "allowed-tools: Read\n---\nBODY\n"
    )
    return path


def broken_skill(tmp_path):
    path = tmp_path / "SKILL.md"
    path.write_text("no frontmatter here\n")
    return path


def refusal_detail(path):
    with pytest.raises(SkillParseError) as caught:
        parse_skill(path)
    return caught.value.detail


def test_parse_refusal_prints_a_human_envelope_and_exits_1(tmp_path, capsys):
    path = broken_skill(tmp_path)
    out = tmp_path / "traces"
    code = main(
        ["check", str(path), *REQUIRED, "--out", str(out)],
        model=object(),
        sandbox=object(),
    )
    captured = capsys.readouterr()
    assert code == 1
    assert captured.out == (
        f"skill: {path}\n"
        "verdict: UNVERIFIED\n"
        "cause: WONT_PARSE\n"
        f"detail: {refusal_detail(path)}\n"
        "exit: 1\n"
    )
    assert captured.err == ""
    assert not out.exists()


def test_parse_refusal_prints_a_canonical_json_envelope(tmp_path, capsys):
    path = broken_skill(tmp_path)
    code = main(
        ["check", str(path), *REQUIRED, "--json"],
        model=object(),
        sandbox=object(),
    )
    captured = capsys.readouterr()
    assert code == 1
    payload = {
        "schema": 1,
        "skill": {"path": str(path)},
        "verdict": "unverified",
        "cause": "wont-parse",
        "detail": refusal_detail(path),
    }
    assert captured.out == (
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
    )
    assert captured.out.count("\n") == 1
    assert captured.err == ""


@pytest.mark.parametrize("as_json", [False, True])
def test_sandbox_unavailable_prints_an_envelope_and_exits_1(
    tmp_path, capsys, monkeypatch, as_json
):
    path = valid_skill(tmp_path)
    out = tmp_path / "traces"

    def unavailable():
        raise SandboxUnavailable("no confining sandbox backend for platform 'linux'")

    monkeypatch.setattr(cli_main, "select_sandbox", unavailable)
    argv = ["check", str(path), *REQUIRED, "--out", str(out)]
    code = main([*argv, "--json"] if as_json else argv, model=object())
    captured = capsys.readouterr()
    assert code == 1
    assert not out.exists()
    if as_json:
        assert captured.out == (
            json.dumps(
                {
                    "schema": 1,
                    "skill": {"path": str(path)},
                    "verdict": "unverified",
                    "cause": "sandbox-unavailable",
                    "detail": "no confining sandbox backend for platform 'linux'",
                },
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            )
            + "\n"
        )
    else:
        assert captured.out == (
            f"skill: {path}\n"
            "verdict: UNVERIFIED\n"
            "cause: SANDBOX_UNAVAILABLE\n"
            "detail: no confining sandbox backend for platform 'linux'\n"
            "exit: 1\n"
        )
    assert captured.err == ""


def test_unexpected_exception_is_one_typed_line_and_exits_2(capsys, monkeypatch):
    def broken(args):
        raise RuntimeError("boom")

    monkeypatch.setattr(cli_main, "parse_skill", broken)
    code = main(["check", "SKILL.md", *REQUIRED], model=object(), sandbox=object())
    captured = capsys.readouterr()
    assert code == 2
    assert captured.out == ""
    assert captured.err == "error: RuntimeError: boom\n"
    assert "Traceback" not in captured.err


def test_keyboard_interrupt_exits_130_without_a_traceback(capsys, monkeypatch):
    def interrupted(args):
        raise KeyboardInterrupt

    monkeypatch.setattr(cli_main, "parse_skill", interrupted)
    code = main(["check", "SKILL.md", *REQUIRED], model=object(), sandbox=object())
    captured = capsys.readouterr()
    assert code == 130
    assert captured.out == ""
    assert "Traceback" not in captured.err


def test_the_api_key_never_appears_in_a_refusal(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-must-not-leak")
    path = broken_skill(tmp_path)
    assert main(["check", str(path), *REQUIRED, "--json"], sandbox=object()) == 1
    captured = capsys.readouterr()
    assert "sk-must-not-leak" not in captured.out + captured.err
