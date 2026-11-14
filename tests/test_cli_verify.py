import importlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from assay.agent import ModelPrice, ToolCall, Usage
from assay.agent.base import ModelReply
from assay.bundle import sign
from assay.canonical import canonical
from assay.cli import main
from assay.sandbox import RunRecord

cli_main = importlib.import_module("assay.cli.main")

PRICE = ModelPrice(input_per_mtok=2.0, output_per_mtok=1.0)
BASE = ["--max-cost", "1", "--model", "fake", "--input-price", "2", "--output-price", "1"]

requires_ssh_keygen = pytest.mark.skipif(
    shutil.which("ssh-keygen") is None, reason="ssh-keygen not installed"
)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in ("ASSAY_MODEL", "ASSAY_INPUT_PRICE", "ASSAY_OUTPUT_PRICE", "ASSAY_MAX_COST"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture(scope="module")
def keypair(tmp_path_factory):
    private_key = tmp_path_factory.mktemp("keys") / "key"
    generate_key(private_key)
    return private_key, private_key.with_suffix(".pub")


def generate_key(path):
    subprocess.run(
        [
            "ssh-keygen",
            "-q",
            "-t",
            "ed25519",
            "-N",
            "",
            "-C",
            "assay-cli-test",
            "-f",
            str(path),
        ],
        check=True,
        capture_output=True,
    )


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


def write_skill(tmp_path):
    path = tmp_path / "SKILL.md"
    path.write_text(
        "---\nname: demo\ndescription: Does a demo.\n"
        "metadata:\n  assay:\n    files: [in.txt]\n    network: []\n"
        "allowed-tools: Read\n---\nBODY\n",
        encoding="utf-8",
    )
    return path


def check_run(tmp_path, monkeypatch, *, undeclared=False):
    root = tmp_path / "run"
    root.mkdir(exist_ok=True)
    monkeypatch.setattr(cli_main, "_make_run_root", lambda: root)
    out = tmp_path / "traces"
    skill_path = write_skill(tmp_path)
    target = "secret.txt" if undeclared else "in.txt"
    model = FakeModel([reply("working", [call("read_file", path=target)]), reply("done")])
    main(
        ["check", str(skill_path), *BASE, "--out", str(out)],
        model=model,
        sandbox=FakeSandbox(),
    )
    return skill_path, next(out.glob("*.json"))


def make_bundle(trace_path, skill_path, private_key):
    return main(
        ["bundle", str(trace_path), "--skill", str(skill_path), "--key", str(private_key)]
    )


def bundle_path_for(trace_path):
    return trace_path.parent / f"{trace_path.stem}.bundle.json"


def rewrite(path, payload):
    path.write_text(canonical(payload), encoding="utf-8")


@requires_ssh_keygen
def test_verify_succeeds_on_a_fresh_bundle(tmp_path, monkeypatch, keypair, capsys):
    private_key, public_key = keypair
    skill_path, trace_path = check_run(tmp_path, monkeypatch)
    capsys.readouterr()
    assert make_bundle(trace_path, skill_path, private_key) == 0
    capsys.readouterr()
    bundle_path = bundle_path_for(trace_path)

    code = main(["verify", str(bundle_path), "--public-key", str(public_key)])

    report = capsys.readouterr().out
    assert code == 0
    assert f"bundle: {bundle_path}\n" in report
    assert "verdict: CLEAN\n" in report
    assert "sandbox: sha256:" in report
    assert "signer: SHA256:" in report
    assert "signature: verified\n" in report
    assert "signature: verified\nreplay: verified\n" in report
    assert "exit: 0\n" in report


@requires_ssh_keygen
def test_a_schema_two_corpus_bundle_still_verifies(tmp_path, keypair, capsys):
    private_key, public_key = keypair
    source = sorted(Path("corpus/cases").glob("*/[0-9a-f]*.json"))[0]
    case_dir = tmp_path / "case"
    case_dir.mkdir()
    shutil.copy2(source, case_dir / source.name)
    shutil.copy2(source.parent / "SKILL.md", case_dir / "SKILL.md")
    trace_path = case_dir / source.name

    assert make_bundle(trace_path, case_dir / "SKILL.md", private_key) == 0
    bundle_path = bundle_path_for(trace_path)
    payload = json.loads(bundle_path.read_text(encoding="utf-8"))
    assert payload["schema"] == 2
    assert payload["trace"]["schema"] == 2
    capsys.readouterr()

    code = main(["verify", str(bundle_path), "--public-key", str(public_key)])

    report = capsys.readouterr().out
    assert code == 0
    assert "signature: verified\nreplay: verified\n" in report
    assert "exit: 0\n" in report


@requires_ssh_keygen
def test_verify_json_reports_verified_true(tmp_path, monkeypatch, keypair, capsys):
    private_key, public_key = keypair
    skill_path, trace_path = check_run(tmp_path, monkeypatch)
    capsys.readouterr()
    assert make_bundle(trace_path, skill_path, private_key) == 0
    capsys.readouterr()
    bundle_path = bundle_path_for(trace_path)

    code = main(["verify", str(bundle_path), "--public-key", str(public_key), "--json"])

    output = capsys.readouterr().out
    payload = json.loads(output)
    assert code == 0
    assert output.count("\n") == 1
    assert output == canonical(payload)
    assert set(payload) == {
        "schema",
        "bundle",
        "skill",
        "assessment",
        "trace_hash",
        "sandbox",
        "signer",
        "verified",
        "replay",
    }
    assert payload["verified"] is True
    assert payload["replay"] is True
    assert payload["trace_hash"] == trace_path.stem
    assert payload["bundle"] == str(bundle_path)


@requires_ssh_keygen
def test_verify_refuses_a_signed_false_assessment(tmp_path, monkeypatch, keypair, capsys):
    private_key, public_key = keypair
    skill_path, trace_path = check_run(tmp_path, monkeypatch, undeclared=True)
    capsys.readouterr()
    assert make_bundle(trace_path, skill_path, private_key) == 0
    capsys.readouterr()
    bundle_path = bundle_path_for(trace_path)
    payload = json.loads(bundle_path.read_text(encoding="utf-8"))
    assert payload["assessment"]["verdict"] == "flagged"

    payload["assessment"]["verdict"] = "clean"
    payload["assessment"]["findings"] = []
    payload["assessment"]["blocked"] = False
    payload["assessment"]["cause"] = None
    unsigned = {key: value for key, value in payload.items() if key != "signature"}
    payload["signature"] = sign(
        canonical(unsigned).encode("utf-8"), private_key
    ).to_payload()
    rewrite(bundle_path, payload)

    code = main(["verify", str(bundle_path), "--public-key", str(public_key)])

    captured = capsys.readouterr()
    assert code == 1
    assert "cause: REPLAY_MISMATCH\n" in captured.out
    assert "signature: verified" not in captured.out
    assert "Traceback" not in captured.out + captured.err


@requires_ssh_keygen
def test_verify_refuses_a_schema_one_bundle(tmp_path, monkeypatch, keypair, capsys):
    private_key, public_key = keypair
    skill_path, trace_path = check_run(tmp_path, monkeypatch)
    capsys.readouterr()
    assert make_bundle(trace_path, skill_path, private_key) == 0
    capsys.readouterr()
    bundle_path = bundle_path_for(trace_path)
    payload = json.loads(bundle_path.read_text(encoding="utf-8"))
    payload["schema"] = 1
    rewrite(bundle_path, payload)

    code = main(["verify", str(bundle_path), "--public-key", str(public_key)])

    captured = capsys.readouterr()
    assert code == 1
    assert "cause: BUNDLE_INVALID\n" in captured.out
    assert "not replayable" in captured.out
    assert "Traceback" not in captured.out + captured.err


@requires_ssh_keygen
def test_verify_refuses_a_flipped_verdict(tmp_path, monkeypatch, keypair, capsys):
    private_key, public_key = keypair
    skill_path, trace_path = check_run(tmp_path, monkeypatch, undeclared=True)
    capsys.readouterr()
    assert make_bundle(trace_path, skill_path, private_key) == 0
    capsys.readouterr()
    bundle_path = bundle_path_for(trace_path)
    payload = json.loads(bundle_path.read_text(encoding="utf-8"))
    assert payload["assessment"]["verdict"] == "flagged"
    payload["assessment"]["verdict"] = "malicious"
    payload["assessment"]["findings"][0]["severity"] = "high"
    payload["assessment"]["findings"][0]["review_required"] = True
    rewrite(bundle_path, payload)

    code = main(["verify", str(bundle_path), "--public-key", str(public_key)])

    captured = capsys.readouterr()
    assert code == 1
    assert "cause: SIGNATURE_INVALID\n" in captured.out
    assert "Traceback" not in captured.out + captured.err


@requires_ssh_keygen
def test_verify_refuses_a_changed_trace_event(tmp_path, monkeypatch, keypair, capsys):
    private_key, public_key = keypair
    skill_path, trace_path = check_run(tmp_path, monkeypatch)
    capsys.readouterr()
    assert make_bundle(trace_path, skill_path, private_key) == 0
    capsys.readouterr()
    bundle_path = bundle_path_for(trace_path)
    payload = json.loads(bundle_path.read_text(encoding="utf-8"))
    payload["trace"]["events"][0]["target"] = "elsewhere.txt"
    rewrite(bundle_path, payload)

    code = main(["verify", str(bundle_path), "--public-key", str(public_key)])

    captured = capsys.readouterr()
    assert code == 1
    assert "cause: HASH_MISMATCH\n" in captured.out
    assert "Traceback" not in captured.out + captured.err


@requires_ssh_keygen
def test_verify_refuses_another_key(tmp_path, monkeypatch, keypair, capsys):
    private_key, _ = keypair
    other = tmp_path / "other"
    generate_key(other)
    skill_path, trace_path = check_run(tmp_path, monkeypatch)
    capsys.readouterr()
    assert make_bundle(trace_path, skill_path, private_key) == 0
    capsys.readouterr()
    bundle_path = bundle_path_for(trace_path)

    code = main(
        ["verify", str(bundle_path), "--public-key", str(other.with_suffix(".pub"))]
    )

    captured = capsys.readouterr()
    assert code == 1
    assert "cause: SIGNER_MISMATCH\n" in captured.out
    assert "Traceback" not in captured.out + captured.err


@requires_ssh_keygen
@pytest.mark.parametrize(
    "mutate, cause",
    [
        (lambda payload: json.dumps(payload, indent=2) + "\n", "bundle-not-canonical"),
        (lambda payload: canonical({**payload, "extra": True}), "bundle-invalid"),
    ],
)
def test_verify_refuses_pretty_printed_and_extra_key_files(
    tmp_path, monkeypatch, keypair, capsys, mutate, cause
):
    private_key, public_key = keypair
    skill_path, trace_path = check_run(tmp_path, monkeypatch)
    capsys.readouterr()
    assert make_bundle(trace_path, skill_path, private_key) == 0
    capsys.readouterr()
    bundle_path = bundle_path_for(trace_path)
    payload = json.loads(bundle_path.read_text(encoding="utf-8"))
    bundle_path.write_text(mutate(payload), encoding="utf-8")

    code = main(["verify", str(bundle_path), "--public-key", str(public_key)])

    captured = capsys.readouterr()
    assert code == 1
    assert f"cause: {cause.upper().replace('-', '_')}\n" in captured.out
    assert "Traceback" not in captured.out + captured.err


@requires_ssh_keygen
def test_verify_refuses_a_missing_bundle_and_bad_public_key(
    tmp_path, monkeypatch, keypair, capsys
):
    private_key, public_key = keypair
    missing = tmp_path / "absent.bundle.json"

    code = main(["verify", str(missing), "--public-key", str(public_key)])

    captured = capsys.readouterr()
    assert code == 1
    assert "cause: BUNDLE_UNREADABLE\n" in captured.out
    assert "Traceback" not in captured.out + captured.err

    skill_path, trace_path = check_run(tmp_path, monkeypatch)
    capsys.readouterr()
    assert make_bundle(trace_path, skill_path, private_key) == 0
    capsys.readouterr()
    bundle_path = bundle_path_for(trace_path)
    not_a_key = tmp_path / "notes.pub"
    not_a_key.write_text("this is not a public key\n", encoding="utf-8")

    code = main(["verify", str(bundle_path), "--public-key", str(not_a_key)])

    captured = capsys.readouterr()
    assert code == 1
    assert "cause: PUBLIC_KEY_INVALID\n" in captured.out
    assert "Traceback" not in captured.out + captured.err


def test_verify_refuses_an_oversized_or_non_utf8_bundle(tmp_path, capsys):
    oversized = tmp_path / "oversized.bundle.json"
    with oversized.open("wb") as handle:
        handle.truncate(64 * 1024 * 1024 + 1)
    code = main(["verify", str(oversized), "--public-key", str(tmp_path / "key.pub")])
    assert code == 1
    assert "cause: BUNDLE_TOO_LARGE\n" in capsys.readouterr().out

    binary = tmp_path / "binary.bundle.json"
    binary.write_bytes(b"\xff\xfe\x00")
    code = main(["verify", str(binary), "--public-key", str(tmp_path / "key.pub")])
    captured = capsys.readouterr()
    assert code == 1
    assert "cause: BUNDLE_INVALID\n" in captured.out
    assert "Traceback" not in captured.out + captured.err


def test_check_output_and_exit_codes_are_unchanged(tmp_path, monkeypatch, capsys):
    root = tmp_path / "run"
    root.mkdir(exist_ok=True)
    monkeypatch.setattr(cli_main, "_make_run_root", lambda: root)
    out = tmp_path / "traces"
    skill_path = write_skill(tmp_path)
    model = FakeModel([reply("working", [call("read_file", path="in.txt")]), reply("done")])

    code = main(
        ["check", str(skill_path), *BASE, "--json", "--out", str(out)],
        model=model,
        sandbox=FakeSandbox(),
    )

    output = capsys.readouterr().out
    payload = json.loads(output)
    assert code == 0
    assert output.count("\n") == 1
    assert output == canonical(payload)
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

    with pytest.raises(SystemExit) as caught:
        main(["check", "--help"])
    assert caught.value.code == 0
    assert "--public-key" not in capsys.readouterr().out
