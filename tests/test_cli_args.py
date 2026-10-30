from pathlib import Path

import pytest

from assay.cli import build_parser, main

REQUIRED = ["--max-cost", "1", "--model", "m", "--input-price", "2", "--output-price", "3"]
ENV = ("ASSAY_MODEL", "ASSAY_INPUT_PRICE", "ASSAY_OUTPUT_PRICE", "ASSAY_MAX_COST")


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in ENV:
        monkeypatch.delenv(name, raising=False)


def skill_file(tmp_path):
    path = tmp_path / "SKILL.md"
    path.write_text(
        "---\nname: demo\ndescription: does a demo\n"
        "metadata:\n  assay:\n    files: [in.txt]\n    network: []\n"
        "allowed-tools: Read\n---\nBODY\n"
    )
    return path


def error_line(capsys):
    err = capsys.readouterr().err
    assert err.count("\n") == 1
    return err.strip()


def test_help_exits_zero_and_names_the_check_command(capsys):
    with pytest.raises(SystemExit) as caught:
        main(["--help"])
    assert caught.value.code == 0
    assert "check" in capsys.readouterr().out


def test_unknown_command_is_an_argparse_error():
    with pytest.raises(SystemExit) as caught:
        main(["nope"])
    assert caught.value.code == 2


def test_missing_skill_is_an_argparse_error():
    with pytest.raises(SystemExit) as caught:
        main(["check", *REQUIRED])
    assert caught.value.code == 2


@pytest.mark.parametrize(
    "drop, flag",
    [
        (["--max-cost", "1"], "--max-cost"),
        (["--model", "m"], "--model"),
        (["--input-price", "2"], "--input-price"),
        (["--output-price", "3"], "--output-price"),
    ],
)
def test_missing_required_setting_is_one_line_and_exit_2(tmp_path, capsys, drop, flag):
    argv = ["check", str(skill_file(tmp_path))]
    for item in REQUIRED:
        if item not in drop:
            argv.append(item)
    assert main(argv) == 2
    assert flag in error_line(capsys)


def test_missing_settings_are_required_even_with_injected_seams(tmp_path, capsys):
    argv = ["check", str(skill_file(tmp_path)), "--model", "m", "--input-price", "2"]
    assert main(argv, model=object(), sandbox=object()) == 2
    assert "--max-cost" in error_line(capsys)


@pytest.mark.parametrize(
    "flag, value",
    [
        ("--max-cost", "0"),
        ("--max-cost", "-1"),
        ("--max-cost", "nan"),
        ("--max-cost", "inf"),
        ("--max-cost", "cheap"),
        ("--input-price", "-1"),
        ("--input-price", "nan"),
        ("--output-price", "-0.1"),
        ("--max-steps", "0"),
        ("--max-steps", "x"),
        ("--max-actions", "0"),
        ("--max-wall-seconds", "0"),
        ("--max-wall-seconds", "soon"),
    ],
)
def test_bad_number_is_one_line_and_exit_2(tmp_path, capsys, flag, value):
    argv = ["check", str(skill_file(tmp_path)), *REQUIRED, flag, value]
    assert main(argv) == 2
    assert flag in error_line(capsys)


def test_defaults_match_the_spec():
    args = build_parser().parse_args(["check", "SKILL.md"])
    assert args.strictness == "standard"
    assert args.max_steps == 20
    assert args.max_actions == 40
    assert args.max_wall_seconds == 300
    assert args.out == Path("./.assay/traces")
    assert args.json is False
    assert args.keep_run_root is False


def test_options_override_every_default():
    args = build_parser().parse_args(
        [
            "check",
            "SKILL.md",
            "--strictness",
            "strict",
            "--max-steps",
            "3",
            "--max-actions",
            "4",
            "--max-wall-seconds",
            "5",
            "--out",
            "traces",
            "--json",
            "--keep-run-root",
        ]
    )
    assert args.strictness == "strict"
    assert int(args.max_steps) == 3
    assert int(args.max_actions) == 4
    assert float(args.max_wall_seconds) == 5
    assert args.out == Path("traces")
    assert args.json is True
    assert args.keep_run_root is True


def test_bad_strictness_is_an_argparse_error():
    with pytest.raises(SystemExit) as caught:
        main(["check", "SKILL.md", *REQUIRED, "--strictness", "paranoid"])
    assert caught.value.code == 2
