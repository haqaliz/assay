import importlib
import json
import shutil
import subprocess

import pytest

from assay.agent import ModelPrice, ToolCall, Usage
from assay.agent.base import ModelReply
from assay.bundle import fingerprint
from assay.canonical import canonical
from assay.capture import TraceStore
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


def write_skill(tmp_path, newline="\n"):
    path = tmp_path / "SKILL.md"
    text = (
        "---\nname: demo\ndescription: Does a demo.\n"
        "metadata:\n  assay:\n    files: [in.txt]\n    network: []\n"
        "allowed-tools: Read\n---\nBODY\n"
    ).replace("\n", newline)
    path.write_bytes(text.encode("utf-8"))
    return path


def check_run(tmp_path, monkeypatch, newline="\n"):
    root = tmp_path / "run"
    root.mkdir(exist_ok=True)
    monkeypatch.setattr(cli_main, "_make_run_root", lambda: root)
    out = tmp_path / "traces"
    skill_path = write_skill(tmp_path, newline)
    model = FakeModel([reply("working", [call("read_file", path="in.txt")]), reply("done")])
    main(
        ["check", str(skill_path), *BASE, "--out", str(out)],
        model=model,
        sandbox=FakeSandbox(),
    )
    return skill_path, next(out.glob("*.json"))


def bundle_path_for(trace_path):
    return trace_path.parent / f"{trace_path.stem}.bundle.json"


@requires_ssh_keygen
def test_bundle_writes_the_canonical_file_next_to_the_trace(
    tmp_path, monkeypatch, keypair, capsys
):
    private_key, public_key = keypair
    skill_path, trace_path = check_run(tmp_path, monkeypatch)
    capsys.readouterr()

    code = main(
        ["bundle", str(trace_path), "--skill", str(skill_path), "--key", str(private_key)]
    )

    assert code == 0
    bundle_path = bundle_path_for(trace_path)
    text = bundle_path.read_text(encoding="utf-8")
    assert text.count("\n") == 1
    payload = json.loads(text)
    trace = TraceStore(trace_path.parent).load(trace_path)
    assert payload["schema"] == 2
    assert payload["hash_list"]["trace"] == trace_path.stem
    assert set(payload["hash_list"]) == {"skill", "trace", "sandbox"}
    assert set(payload["skill"]) == {"content_hash", "source"}
    assert payload["skill"]["content_hash"] == "sha256:" + trace.skill_content_hash
    assert payload["skill"]["source"] == skill_path.read_bytes().decode("utf-8")
    assert payload["signature"]["namespace"] == "assay"
    assert payload["signature"]["value"].startswith("-----BEGIN SSH SIGNATURE-----")
    report = capsys.readouterr().out
    assert f"bundle: {bundle_path.resolve()}\n" in report
    assert "signer: SHA256:" in report
    assert "exit: 0\n" in report

    code = main(["verify", str(bundle_path), "--public-key", str(public_key)])

    report = capsys.readouterr().out
    assert code == 0
    assert "signature: verified\n" in report
    assert "replay: verified\n" in report


@requires_ssh_keygen
def test_bundle_embeds_the_exact_crlf_source(tmp_path, monkeypatch, keypair, capsys):
    private_key, public_key = keypair
    skill_path, trace_path = check_run(tmp_path, monkeypatch, newline="\r\n")
    capsys.readouterr()

    code = main(
        ["bundle", str(trace_path), "--skill", str(skill_path), "--key", str(private_key)]
    )

    assert code == 0
    capsys.readouterr()
    raw = skill_path.read_bytes().decode("utf-8")
    assert "\r\n" in raw
    bundle_path = bundle_path_for(trace_path)
    payload = json.loads(bundle_path.read_text(encoding="utf-8"))
    trace = TraceStore(trace_path.parent).load(trace_path)
    assert payload["skill"]["source"] == raw
    assert payload["skill"]["content_hash"] == "sha256:" + trace.skill_content_hash

    code = main(["verify", str(bundle_path), "--public-key", str(public_key)])

    assert code == 0
    assert "replay: verified\n" in capsys.readouterr().out


@requires_ssh_keygen
def test_bundle_out_overrides_and_creates_the_directory(
    tmp_path, monkeypatch, keypair, capsys
):
    private_key, _ = keypair
    skill_path, trace_path = check_run(tmp_path, monkeypatch)
    capsys.readouterr()
    out = tmp_path / "nested" / "bundles"

    code = main(
        [
            "bundle",
            str(trace_path),
            "--skill",
            str(skill_path),
            "--key",
            str(private_key),
            "--out",
            str(out),
        ]
    )

    assert code == 0
    assert (out / f"{trace_path.stem}.bundle.json").is_file()
    assert not bundle_path_for(trace_path).exists()
    assert f"bundle: {(out / f'{trace_path.stem}.bundle.json').resolve()}\n" in (
        capsys.readouterr().out
    )


@requires_ssh_keygen
def test_bundle_json_is_canonical_and_names_the_signer(
    tmp_path, monkeypatch, keypair, capsys
):
    private_key, public_key = keypair
    skill_path, trace_path = check_run(tmp_path, monkeypatch)
    capsys.readouterr()

    code = main(
        [
            "bundle",
            str(trace_path),
            "--skill",
            str(skill_path),
            "--key",
            str(private_key),
            "--json",
        ]
    )

    output = capsys.readouterr().out
    payload = json.loads(output)
    trace = TraceStore(trace_path.parent).load(trace_path)
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
    }
    assert payload["schema"] == 1
    assert payload["bundle"] == str(bundle_path_for(trace_path).resolve())
    assert payload["skill"] == {
        "name": "demo",
        "content_hash": "sha256:" + trace.skill_content_hash,
    }
    assert payload["sandbox"] == list(trace.sandbox_config_hashes)
    assert payload["assessment"]["verdict"] == "clean"
    assert payload["assessment"]["strictness"] == "standard"
    assert payload["signer"] == fingerprint(public_key)


def test_bundle_refuses_a_modified_skill(tmp_path, monkeypatch, capsys):
    skill_path, trace_path = check_run(tmp_path, monkeypatch)
    skill_path.write_text(skill_path.read_text(encoding="utf-8") + "\nchanged\n", encoding="utf-8")
    capsys.readouterr()

    code = main(
        [
            "bundle",
            str(trace_path),
            "--skill",
            str(skill_path),
            "--key",
            str(tmp_path / "unused-key"),
        ]
    )

    captured = capsys.readouterr()
    assert code == 1
    assert "cause: SKILL_MISMATCH\n" in captured.out
    assert not bundle_path_for(trace_path).exists()
    assert "Traceback" not in captured.out + captured.err


@requires_ssh_keygen
def test_bundle_refuses_an_unreadable_trace_and_bad_key(tmp_path, monkeypatch, capsys):
    skill_path, trace_path = check_run(tmp_path, monkeypatch)
    capsys.readouterr()

    missing = tmp_path / "absent" / "trace.json"
    code = main(
        ["bundle", str(missing), "--skill", str(skill_path), "--key", str(tmp_path / "no-key")]
    )
    assert code == 1
    assert "cause: TRACE_UNREADABLE\n" in capsys.readouterr().out

    bad = tmp_path / "bad.json"
    bad.write_text("{}", encoding="utf-8")
    code = main(
        ["bundle", str(bad), "--skill", str(skill_path), "--key", str(tmp_path / "no-key")]
    )
    assert code == 1
    assert "cause: TRACE_INVALID\n" in capsys.readouterr().out

    code = main(
        [
            "bundle",
            str(trace_path),
            "--skill",
            str(skill_path),
            "--key",
            str(tmp_path / "missing-key"),
        ]
    )
    captured = capsys.readouterr()
    assert code == 1
    assert "cause: SIGNING_KEY_UNAVAILABLE\n" in captured.out
    assert "Traceback" not in captured.out + captured.err


def test_bundle_failure_json_envelope_has_schema_bundle_cause_detail(
    tmp_path, capsys
):
    missing = tmp_path / "absent" / "trace.json"
    code = main(
        [
            "bundle",
            str(missing),
            "--skill",
            str(tmp_path / "SKILL.md"),
            "--key",
            str(tmp_path / "key"),
            "--json",
        ]
    )

    output = capsys.readouterr().out
    payload = json.loads(output)
    assert code == 1
    assert output.count("\n") == 1
    assert output == canonical(payload)
    assert set(payload) == {"schema", "bundle", "cause", "detail"}
    assert payload["schema"] == 1
    assert payload["cause"] == "trace-unreadable"
    assert payload["bundle"] == str(
        (missing.parent / f"{missing.stem}.bundle.json").resolve()
    )
    assert payload["detail"]


@requires_ssh_keygen
def test_bundle_does_not_print_the_private_key_path(tmp_path, monkeypatch, keypair, capsys):
    skill_path, trace_path = check_run(tmp_path, monkeypatch)
    capsys.readouterr()
    sentinel = tmp_path / "private-key-sentinel-9f3d"

    code = main(
        ["bundle", str(trace_path), "--skill", str(skill_path), "--key", str(sentinel)]
    )

    captured = capsys.readouterr()
    assert code == 1
    assert "cause: SIGNING_KEY_UNAVAILABLE\n" in captured.out
    assert sentinel.name not in captured.out + captured.err
    assert not bundle_path_for(trace_path).exists()


def test_bundle_refuses_a_broken_skill_directory(tmp_path, monkeypatch, capsys):
    _, trace_path = check_run(tmp_path, monkeypatch)
    broken = tmp_path / "broken-skill"
    broken.mkdir()
    (broken / "SKILL.md").write_text("no frontmatter here\n", encoding="utf-8")
    capsys.readouterr()

    code = main(
        [
            "bundle",
            str(trace_path),
            "--skill",
            str(broken),
            "--key",
            str(tmp_path / "unused-key"),
        ]
    )

    captured = capsys.readouterr()
    assert code == 1
    assert "cause: SKILL_INVALID\n" in captured.out
    assert not bundle_path_for(trace_path).exists()


@requires_ssh_keygen
def test_bundle_refuses_an_invalid_bundle_destination(
    tmp_path, monkeypatch, keypair, capsys
):
    private_key, _ = keypair
    skill_path, trace_path = check_run(tmp_path, monkeypatch)
    capsys.readouterr()
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("x", encoding="utf-8")

    code = main(
        [
            "bundle",
            str(trace_path),
            "--skill",
            str(skill_path),
            "--key",
            str(private_key),
            "--out",
            str(blocker),
        ]
    )

    captured = capsys.readouterr()
    assert code == 1
    assert "cause: BUNDLE_WRITE_FAILED\n" in captured.out
    assert "Traceback" not in captured.out + captured.err
