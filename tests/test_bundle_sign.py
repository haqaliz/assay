from __future__ import annotations

import importlib
import shutil
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from assay.bundle import (
    BundleError,
    SigningError,
    build,
    fingerprint,
    replay,
    sign,
    verify,
)
from assay.bundle.sign import verify as verify_signature
from assay.capture import Event, EventKind, EventOutcome, Trace
from assay.ingest import Skill, parse_skill_text
from assay.verdict import Strictness, Verdict

requires_ssh_keygen = pytest.mark.skipif(
    shutil.which("ssh-keygen") is None, reason="ssh-keygen not installed"
)

SOURCE = (
    "---\n"
    "name: demo\n"
    "description: reads one declared file\n"
    "allowed-tools: Read\n"
    "metadata:\n"
    "  assay:\n"
    '    files: ["in.txt"]\n'
    "    network: []\n"
    "---\n"
    "Read in.txt.\n"
)


def generate_key(private_key: Path, comment: str = "assay-test") -> None:
    subprocess.run(
        [
            "ssh-keygen",
            "-q",
            "-t",
            "ed25519",
            "-N",
            "",
            "-C",
            comment,
            "-f",
            str(private_key),
        ],
        check=True,
        capture_output=True,
    )


@pytest.fixture(scope="module")
def keypair(tmp_path_factory) -> tuple[Path, Path]:
    private_key = tmp_path_factory.mktemp("keys") / "key"
    generate_key(private_key)
    return private_key, private_key.with_suffix(".pub")


def skill() -> Skill:
    return parse_skill_text(SOURCE)


def trace(*, undeclared: bool = False) -> Trace:
    return Trace(
        skill_name="demo",
        skill_content_hash=skill().content_hash,
        task_sha256="b" * 64,
        cause=None,
        input_tokens=12,
        output_tokens=3,
        cost_usd=0.0012,
        events=(
            Event(
                kind=EventKind.FILE_READ,
                outcome=EventOutcome.OK,
                target="secret.txt" if undeclared else "in.txt",
                content_sha256="c" * 64,
                content_bytes=5,
                excerpt="hello",
            ),
        ),
        sandbox_config_hashes=(),
    )


@requires_ssh_keygen
def test_sign_and_verify_round_trip(keypair):
    private_key, public_key = keypair

    signature = sign(b"payload", private_key)

    assert signature.signer == fingerprint(public_key)
    assert verify_signature(b"payload", signature, public_key) is None


@requires_ssh_keygen
def test_signature_is_deterministic(keypair):
    private_key, _ = keypair

    first = sign(b"payload", private_key)
    second = sign(b"payload", private_key)

    assert first.value == second.value


@requires_ssh_keygen
def test_tampered_payload_fails(keypair):
    private_key, public_key = keypair
    signature = sign(b"payload", private_key)

    with pytest.raises(SigningError, match="signature-invalid"):
        verify_signature(b"payloaX", signature, public_key)


@requires_ssh_keygen
def test_wrong_public_key_fails(tmp_path, keypair):
    private_key, _ = keypair
    generate_key(tmp_path / "other")
    signature = sign(b"payload", private_key)

    with pytest.raises(SigningError, match="signer-mismatch"):
        verify_signature(b"payload", signature, tmp_path / "other.pub")


def test_missing_ssh_keygen_is_named(monkeypatch, tmp_path):
    monkeypatch.setattr(shutil, "which", lambda name: None)

    with pytest.raises(SigningError, match="ssh-keygen-not-found"):
        sign(b"payload", tmp_path / "key")


@requires_ssh_keygen
def test_public_key_with_two_lines_is_refused(tmp_path, keypair):
    _, public_key = keypair
    generate_key(tmp_path / "other")
    doubled = tmp_path / "two.pub"
    doubled.write_text(
        public_key.read_text(encoding="utf-8")
        + (tmp_path / "other.pub").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    with pytest.raises(SigningError, match="public-key-invalid"):
        fingerprint(doubled)


@requires_ssh_keygen
def test_private_key_material_never_appears_in_the_signature(tmp_path):
    sentinel = "sentinel-8f3d2c"
    private_key = tmp_path / "key"
    generate_key(private_key, comment=sentinel)

    signature = sign(b"payload", private_key)

    assert sentinel not in signature.value
    assert "PRIVATE KEY" not in signature.value
    assert sentinel not in repr(signature)
    assert "PRIVATE KEY" not in repr(signature)


@requires_ssh_keygen
def test_build_and_verify_convenience_functions(keypair):
    private_key, public_key = keypair
    skill_record, trace_record = skill(), trace()

    bundle = build(skill_record, SOURCE, trace_record, Strictness.STANDARD, private_key)

    assert verify(bundle, public_key) is None
    assert replay(bundle) == bundle.assessment
    assert bundle.assessment.verdict is Verdict.CLEAN
    payload = bundle.to_payload()
    assert payload["signature"]["signer"] == fingerprint(public_key)
    assert payload["hash_list"] == {
        "skill": "sha256:" + skill_record.content_hash,
        "trace": trace_record.hash,
        "sandbox": [],
    }
    assert payload["skill"] == {
        "content_hash": "sha256:" + skill_record.content_hash,
        "source": SOURCE,
    }


@requires_ssh_keygen
def test_verify_refuses_a_signed_false_assessment(keypair):
    private_key, public_key = keypair
    bundle = build(skill(), SOURCE, trace(undeclared=True), Strictness.STANDARD, private_key)
    assert bundle.assessment.verdict is Verdict.FLAGGED

    false = replace(
        bundle.assessment,
        verdict=Verdict.CLEAN,
        findings=(),
        cause=None,
        blocked=False,
    )
    unsigned = replace(bundle, assessment=false)
    falsified = replace(
        unsigned,
        signature=sign(unsigned.unsigned_json().encode("utf-8"), private_key),
    )

    with pytest.raises(BundleError, match="^replay-mismatch:"):
        replay(falsified)
    with pytest.raises(BundleError, match="^replay-mismatch:"):
        verify(falsified, public_key)


def test_public_key_that_is_not_a_key_is_refused(tmp_path):
    path = tmp_path / "notes.pub"
    path.write_text("this is not a public key\n", encoding="utf-8")

    with pytest.raises(SigningError, match="public-key-invalid"):
        fingerprint(path)


@requires_ssh_keygen
def test_missing_private_key_is_named_without_echoing_the_path(tmp_path):
    private_key = tmp_path / "missing-key"

    with pytest.raises(SigningError, match="signing-key-unavailable") as caught:
        sign(b"payload", private_key)

    assert str(private_key) not in str(caught.value)


@requires_ssh_keygen
def test_encrypted_key_failure_does_not_echo_the_path(tmp_path, monkeypatch):
    private_key = tmp_path / "locked-key"
    subprocess.run(
        ["ssh-keygen", "-q", "-t", "ed25519", "-N", "secret", "-f", str(private_key)],
        check=True,
        capture_output=True,
    )
    monkeypatch.setattr(importlib.import_module("assay.bundle.sign"), "SIGN_TIMEOUT", 2)

    with pytest.raises(SigningError) as caught:
        sign(b"payload", private_key)

    assert str(private_key) not in str(caught.value)
