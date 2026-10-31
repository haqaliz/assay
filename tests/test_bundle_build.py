from dataclasses import replace
from pathlib import Path

import pytest

from assay.bundle import (
    BundleError,
    Signature,
    create_bundle,
    hash_list_for,
    verify_bundle,
)
from assay.capture import Event, EventKind, EventOutcome, Trace
from assay.ingest import Scope, Skill
from assay.verdict import (
    Strictness,
    StrictnessPolicy,
    UnverifiedCause,
    Verdict,
    assess,
)


def signature(**over):
    base = dict(
        signer="SHA256:" + "A" * 43,
        value=(
            "-----BEGIN SSH SIGNATURE-----\n"
            "AAAAB3NzaC1yc2E=\n"
            "-----END SSH SIGNATURE-----\n"
        ),
    )
    base.update(over)
    return Signature(**base)


def skill(**over):
    base = dict(
        name="demo",
        description="reads one declared file",
        scope=Scope(tools=frozenset({"Read"}), files=("in.txt",), network=()),
        body="Read in.txt and summarise it.",
        source_path=Path("SKILL.md"),
        content_hash="a" * 64,
    )
    base.update(over)
    return Skill(**base)


def trace(**over):
    base = dict(
        skill_name="demo",
        skill_content_hash="a" * 64,
        task_sha256="b" * 64,
        cause=None,
        input_tokens=12,
        output_tokens=3,
        cost_usd=0.0012,
        events=(
            Event(
                kind=EventKind.FILE_READ,
                outcome=EventOutcome.OK,
                target="in.txt",
                content_sha256="c" * 64,
                content_bytes=5,
                excerpt="hello",
            ),
        ),
        sandbox_config_hashes=(),
    )
    base.update(over)
    return Trace(**base)


def recording_signer(seen):
    def sign(payload: bytes) -> Signature:
        seen.append(payload)
        return signature()

    return sign


def test_create_bundle_uses_assess_and_signs_the_unsigned_payload():
    seen = []

    bundle = create_bundle(skill(), trace(), Strictness.STANDARD, recording_signer(seen))

    expected = assess(
        skill(), trace(), policy=StrictnessPolicy(level=Strictness.STANDARD)
    )
    assert bundle.assessment == expected
    assert bundle.assessment.verdict is Verdict.CLEAN
    assert bundle.hash_list == hash_list_for(trace(), expected)
    assert bundle.signature == signature()
    assert seen == [bundle.unsigned_json().encode("utf-8")]


def test_create_bundle_refuses_a_skill_that_did_not_produce_the_trace():
    seen = []
    other = replace(skill(), content_hash="b" * 64)

    with pytest.raises(BundleError, match="skill-mismatch"):
        create_bundle(other, trace(), Strictness.STANDARD, recording_signer(seen))

    assert seen == []


def test_verify_bundle_passes_the_signed_bytes_to_the_verifier():
    bundle = create_bundle(skill(), trace(), Strictness.STANDARD, recording_signer([]))
    seen = []

    def verifier(payload: bytes, signature: Signature) -> None:
        seen.append((payload, signature))

    assert verify_bundle(bundle, verifier) is None
    assert seen == [(bundle.unsigned_json().encode("utf-8"), bundle.signature)]


def test_empty_sandbox_hashes_and_unverified_traces_still_bundle():
    # The trace stop vocabulary is step-limit/action-limit/wall-limit; assess maps it to
    # UnverifiedCause.BUDGET_LIMIT.
    stopped = trace(cause="step-limit")
    bundle = create_bundle(skill(), stopped, Strictness.STANDARD, recording_signer([]))
    seen = []

    def verifier(payload: bytes, signature: Signature) -> None:
        seen.append((payload, signature))

    verify_bundle(bundle, verifier)

    assert bundle.assessment.verdict is Verdict.UNVERIFIED
    assert bundle.assessment.cause is UnverifiedCause.BUDGET_LIMIT
    assert bundle.to_payload()["hash_list"]["sandbox"] == []
    assert seen == [(bundle.unsigned_json().encode("utf-8"), bundle.signature)]
