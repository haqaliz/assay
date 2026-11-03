import hashlib
from dataclasses import replace

import pytest

from assay.bundle import (
    Bundle,
    BundleError,
    Signature,
    SkillSource,
    create_bundle,
    hash_list_for,
    replay,
    verify_bundle,
)
from assay.capture import Event, EventKind, EventOutcome, Trace
from assay.ingest import parse_skill_text
from assay.verdict import (
    Assessment,
    Strictness,
    StrictnessPolicy,
    UnverifiedCause,
    Verdict,
    assess,
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
SKILL = parse_skill_text(SOURCE)


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


def trace(**over):
    base = dict(
        skill_name="demo",
        skill_content_hash=SKILL.content_hash,
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


def test_create_bundle_uses_assess_and_signs_the_unsigned_payload_including_the_skill():
    seen = []

    bundle = create_bundle(SKILL, SOURCE, trace(), Strictness.STANDARD, recording_signer(seen))

    expected = assess(
        SKILL, trace(), policy=StrictnessPolicy(level=Strictness.STANDARD)
    )
    assert bundle.assessment == expected
    assert bundle.assessment.verdict is Verdict.CLEAN
    assert bundle.skill == SkillSource("sha256:" + SKILL.content_hash, SOURCE)
    assert bundle.hash_list == hash_list_for(trace(), expected)
    assert bundle.signature == signature()
    assert seen == [bundle.unsigned_json().encode("utf-8")]


def test_create_bundle_refuses_a_source_that_did_not_produce_the_skill():
    seen = []

    with pytest.raises(BundleError, match="skill-mismatch"):
        create_bundle(
            SKILL, SOURCE + "\nchanged\n", trace(), Strictness.STANDARD, recording_signer(seen)
        )
    with pytest.raises(BundleError, match="skill-mismatch"):
        create_bundle(
            replace(SKILL, content_hash="b" * 64),
            SOURCE,
            trace(),
            Strictness.STANDARD,
            recording_signer(seen),
        )

    assert seen == []


def test_create_bundle_refuses_a_non_text_source():
    with pytest.raises(BundleError, match="skill-mismatch"):
        create_bundle(SKILL, None, trace(), Strictness.STANDARD, recording_signer([]))


def test_verify_bundle_passes_the_signed_bytes_to_the_verifier():
    bundle = create_bundle(SKILL, SOURCE, trace(), Strictness.STANDARD, recording_signer([]))
    seen = []

    def verifier(payload: bytes, signature: Signature) -> None:
        seen.append((payload, signature))

    assert verify_bundle(bundle, verifier) is None
    assert seen == [(bundle.unsigned_json().encode("utf-8"), bundle.signature)]


def test_empty_sandbox_hashes_and_unverified_traces_still_bundle():
    # The trace stop vocabulary is step-limit/action-limit/wall-limit; assess maps it to
    # UnverifiedCause.BUDGET_LIMIT.
    stopped = trace(cause="step-limit")
    bundle = create_bundle(SKILL, SOURCE, stopped, Strictness.STANDARD, recording_signer([]))
    seen = []

    def verifier(payload: bytes, signature: Signature) -> None:
        seen.append((payload, signature))

    verify_bundle(bundle, verifier)

    assert bundle.assessment.verdict is Verdict.UNVERIFIED
    assert bundle.assessment.cause is UnverifiedCause.BUDGET_LIMIT
    assert bundle.to_payload()["hash_list"]["sandbox"] == []
    assert seen == [(bundle.unsigned_json().encode("utf-8"), bundle.signature)]


def test_replay_rederives_and_returns_the_stored_assessment():
    bundle = create_bundle(SKILL, SOURCE, trace(), Strictness.STANDARD, recording_signer([]))

    assert replay(bundle) == bundle.assessment


def test_replay_refuses_an_assessment_that_does_not_follow():
    undeclared = trace(
        events=(
            Event(
                kind=EventKind.FILE_READ,
                outcome=EventOutcome.OK,
                target="secret.txt",
                content_sha256="c" * 64,
                content_bytes=5,
                excerpt="hello",
            ),
        )
    )
    bundle = create_bundle(
        SKILL, SOURCE, undeclared, Strictness.STANDARD, recording_signer([])
    )
    assert bundle.assessment.verdict is Verdict.FLAGGED

    false = replace(
        bundle.assessment,
        verdict=Verdict.CLEAN,
        findings=(),
        cause=None,
        blocked=False,
    )
    falsified = replace(bundle, assessment=false)

    with pytest.raises(BundleError, match="^replay-mismatch:"):
        replay(falsified)


def test_replay_refuses_a_stored_skill_that_does_not_parse():
    bad_source = "no frontmatter here\n"
    bad_hash = hashlib.sha256(bad_source.encode("utf-8")).hexdigest()
    bad_trace = replace(trace(), skill_content_hash=bad_hash)
    bad_assessment = Assessment(
        verdict=Verdict.CLEAN,
        findings=(),
        cause=None,
        blocked=False,
        strictness=Strictness.STANDARD,
        skill_content_hash=bad_hash,
        trace_hash=bad_trace.hash,
    )
    bundle = Bundle(
        skill=SkillSource("sha256:" + bad_hash, bad_source),
        hash_list=hash_list_for(bad_trace, bad_assessment),
        trace=bad_trace,
        assessment=bad_assessment,
        signature=signature(),
    )

    with pytest.raises(BundleError, match="^replay-mismatch: stored skill does not parse"):
        replay(bundle)
