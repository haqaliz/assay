import hashlib
import json

import pytest

from assay.bundle import (
    BUNDLE_SCHEMA,
    NAMESPACE,
    Bundle,
    BundleError,
    HashList,
    Signature,
    SkillSource,
)
from assay.canonical import canonical
from assay.capture import Event, EventKind, EventOutcome, Trace
from assay.ingest import MAX_SKILL_BYTES, parse_skill_text
from assay.verdict import Assessment, Finding, FindingClass, Severity, Strictness, Verdict

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


def clean_assessment(trace):
    return Assessment(
        verdict=Verdict.CLEAN,
        findings=(),
        cause=None,
        blocked=False,
        strictness=Strictness.STANDARD,
        skill_content_hash=trace.skill_content_hash,
        trace_hash=trace.hash,
    )


def hash_list_for(trace_, **over):
    base = dict(
        skill="sha256:" + trace_.skill_content_hash,
        trace=trace_.hash,
        sandbox=trace_.sandbox_config_hashes,
    )
    base.update(over)
    return HashList(**base)


def skill_source(trace_=None, **over):
    trace_ = trace() if trace_ is None else trace_
    base = dict(
        content_hash="sha256:" + trace_.skill_content_hash,
        source=SOURCE,
    )
    base.update(over)
    return SkillSource(**base)


def make_bundle(trace_=None, **over):
    trace_ = trace() if trace_ is None else trace_
    values = dict(
        skill=skill_source(trace_),
        hash_list=hash_list_for(trace_),
        trace=trace_,
        assessment=clean_assessment(trace_),
        signature=signature(),
    )
    values.update(over)
    return Bundle(**values)


def test_valid_bundle_has_the_exact_canonical_payload():
    first = "sha256:" + "a" * 64
    second = "sha256:" + "b" * 64
    trace_ = trace(sandbox_config_hashes=(second, first, second))
    record = make_bundle(trace_)

    payload = record.to_payload()

    assert set(payload) == {
        "schema",
        "hash_list",
        "skill",
        "trace",
        "assessment",
        "signature",
    }
    assert payload["schema"] == BUNDLE_SCHEMA == 2
    assert payload["hash_list"] == {
        "skill": "sha256:" + trace_.skill_content_hash,
        "trace": trace_.hash,
        "sandbox": [first, second],
    }
    assert payload["skill"] == {
        "content_hash": "sha256:" + trace_.skill_content_hash,
        "source": SOURCE,
    }
    assert payload["trace"] == trace_.to_payload()
    assert payload["assessment"] == clean_assessment(trace_).to_payload()
    assert payload["signature"] == {
        "namespace": NAMESPACE,
        "signer": "SHA256:" + "A" * 43,
        "value": signature().value,
    }

    text = record.to_json()
    assert text == canonical(payload)
    assert text.endswith("\n")
    assert text.count("\n") == 1


@pytest.mark.parametrize(
    "field, value",
    [
        ("skill", "sha256:" + "d" * 64),
        ("trace", "d" * 64),
        ("sandbox", ("sha256:" + "d" * 64,)),
    ],
)
def test_hash_list_disagreement_is_refused(field, value):
    trace_ = trace()
    with pytest.raises(BundleError, match="^hash-mismatch:"):
        make_bundle(trace_, hash_list=hash_list_for(trace_, **{field: value}))


def test_bundle_refuses_a_skill_source_that_is_not_the_traced_skill():
    other = SkillSource("sha256:" + hashlib.sha256(b"other").hexdigest(), "other")

    with pytest.raises(BundleError, match="^hash-mismatch:"):
        make_bundle(skill=other)


def test_non_canonical_bundle_is_refused():
    text = make_bundle().to_json()
    pretty = json.dumps(json.loads(text), indent=2) + "\n"

    with pytest.raises(BundleError, match="bundle-not-canonical"):
        Bundle.from_json(pretty)
    with pytest.raises(BundleError, match="bundle-not-canonical"):
        Bundle.from_json(text + "\n")

    extra = json.loads(text)
    extra["note"] = "unsigned"
    with pytest.raises(BundleError, match="bundle-invalid"):
        Bundle.from_json(canonical(extra))

    extra_hash = json.loads(text)
    extra_hash["hash_list"]["note"] = "unsigned"
    with pytest.raises(BundleError, match="bundle-invalid"):
        Bundle.from_json(canonical(extra_hash))

    extra_skill = json.loads(text)
    extra_skill["skill"]["note"] = "unsigned"
    with pytest.raises(BundleError, match="bundle-invalid"):
        Bundle.from_json(canonical(extra_skill))


@pytest.mark.parametrize("text", ["", "null", "[]", "{"])
def test_malformed_bundle_json_is_a_bundle_error(text):
    with pytest.raises(BundleError, match="bundle-invalid"):
        Bundle.from_json(text)


def test_bundle_round_trips_through_json():
    trace_ = trace(sandbox_config_hashes=("sha256:" + "a" * 64,))
    record = make_bundle(trace_)

    assert Bundle.from_json(record.to_json()) == record


def test_bundle_skill_source_errors_are_bundle_invalid():
    text = make_bundle().to_json()

    missing = json.loads(text)
    del missing["skill"]
    with pytest.raises(BundleError, match="bundle-invalid"):
        Bundle.from_json(canonical(missing))

    not_an_object = json.loads(text)
    not_an_object["skill"] = "source"
    with pytest.raises(BundleError, match="bundle-invalid"):
        Bundle.from_json(canonical(not_an_object))

    changed_source = json.loads(text)
    changed_source["skill"]["source"] = SOURCE + "changed"
    with pytest.raises(BundleError, match="bundle-invalid"):
        Bundle.from_json(canonical(changed_source))

    changed_hash = json.loads(text)
    changed_hash["skill"]["content_hash"] = "sha256:" + "d" * 64
    with pytest.raises(BundleError, match="bundle-invalid"):
        Bundle.from_json(canonical(changed_hash))


@pytest.mark.parametrize("schema", [1, True, "2", 2.0, 3])
def test_bundle_schema_must_be_the_int_two(schema):
    with pytest.raises(BundleError, match="schema"):
        make_bundle(schema=schema)

    payload = json.loads(make_bundle().to_json())
    payload["schema"] = schema
    with pytest.raises(BundleError, match="bundle-invalid"):
        Bundle.from_json(canonical(payload))


def test_schema_one_bundle_is_refused_as_not_replayable():
    payload = json.loads(make_bundle().to_json())
    payload["schema"] = 1

    with pytest.raises(BundleError, match="schema 1 is not replayable"):
        Bundle.from_json(canonical(payload))

    del payload["skill"]
    with pytest.raises(BundleError, match="schema 1 is not replayable"):
        Bundle.from_json(canonical(payload))


def test_unsigned_payload_omits_only_the_signature():
    record = make_bundle()

    unsigned = record.unsigned_payload()

    assert set(unsigned) == set(record.to_payload()) - {"signature"}
    assert unsigned == {
        key: value for key, value in record.to_payload().items() if key != "signature"
    }
    assert record.unsigned_json() == canonical(unsigned)


def test_signature_shape_is_validated():
    signature()
    Signature(
        signer="SHA256:" + "A" * 43,
        value="-----BEGIN SSH SIGNATURE-----\nx\n-----END SSH SIGNATURE-----",
    )

    for over, match in [
        ({"namespace": "other"}, "namespace"),
        ({"signer": "sha256:" + "A" * 43}, "signer"),
        ({"signer": "SHA256:"}, "signer"),
        ({"signer": "not-a-signer"}, "signer"),
        ({"value": "-----BEGIN SSH SIGNATURE-----\nx\n"}, "value"),
        ({"value": "not armored"}, "value"),
    ]:
        with pytest.raises(BundleError, match=match):
            signature(**over)


def test_hash_list_format_is_validated_and_normalised():
    first = "sha256:" + "a" * 64
    second = "sha256:" + "b" * 64

    assert HashList(
        skill=first, trace="c" * 64, sandbox=(second, first, second)
    ).sandbox == (first, second)

    base = dict(skill=first, trace="c" * 64, sandbox=())
    for over, match in [
        ({"skill": "a" * 64}, "skill"),
        ({"skill": "sha256:" + "A" * 64}, "skill"),
        ({"trace": "sha256:" + "c" * 64}, "trace"),
        ({"trace": "C" * 64}, "trace"),
        ({"sandbox": ("c" * 64,)}, "sandbox"),
        ({"sandbox": first}, "sandbox"),
    ]:
        with pytest.raises(BundleError, match=match):
            HashList(**{**base, **over})


def test_skill_source_format_is_validated():
    source = skill_source()
    assert source.content_hash == "sha256:" + SKILL.content_hash
    assert source.source == SOURCE

    for content_hash in ("a" * 64, "sha256:" + "A" * 64, "sha256:" + "a" * 63):
        with pytest.raises(BundleError, match="content_hash"):
            SkillSource(content_hash, SOURCE)

    with pytest.raises(BundleError, match="^hash-mismatch:"):
        SkillSource("sha256:" + "a" * 64, SOURCE)


def test_skill_source_refuses_a_non_string_or_empty_source():
    for source in ("", None, b"---\n"):
        with pytest.raises(BundleError, match="non-empty string"):
            SkillSource("sha256:" + SKILL.content_hash, source)


def test_skill_source_refuses_unencodable_text():
    with pytest.raises(BundleError, match="UTF-8"):
        SkillSource("sha256:" + "a" * 64, "---\nname: \ud800\n---\n")


def test_skill_source_refuses_an_oversized_source():
    oversized = "x" * (MAX_SKILL_BYTES + 1)

    with pytest.raises(BundleError, match=f"limit is {MAX_SKILL_BYTES}"):
        SkillSource("sha256:" + hashlib.sha256(oversized.encode("utf-8")).hexdigest(), oversized)


def test_invalid_embedded_trace_or_assessment_is_a_bundle_error():
    text = make_bundle().to_json()

    old_trace = json.loads(text)
    old_trace["trace"]["schema"] = 1
    with pytest.raises(BundleError, match="bundle-invalid"):
        Bundle.from_json(canonical(old_trace))

    finding = Finding(
        class_=FindingClass.SHELL,
        severity=Severity.REVIEW,
        target="rm -rf /",
        reason="dangerous shell pattern",
        outcome=EventOutcome.OK,
    )
    clean_with_findings = json.loads(text)
    clean_with_findings["assessment"]["findings"] = [finding.to_payload()]
    with pytest.raises(BundleError, match="bundle-invalid"):
        Bundle.from_json(canonical(clean_with_findings))

    unverified = json.loads(text)
    unverified["assessment"]["verdict"] = "unverified"
    with pytest.raises(BundleError, match="bundle-invalid"):
        Bundle.from_json(canonical(unverified))
