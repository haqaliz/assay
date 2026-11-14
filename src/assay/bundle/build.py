"""Build one assessed run into a bundle, verify its signature, and replay its verdict."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Callable

from assay.canonical import canonical
from assay.capture import CaptureError, Trace
from assay.ingest import Format, Skill, SkillParseError, parse_skill_text
from assay.verdict import (
    Assessment,
    Strictness,
    StrictnessPolicy,
    VerdictError,
    assess,
)

from .records import (
    Bundle,
    BundleError,
    HashList,
    Signature,
    SkillSource,
)
from .sign import sign as sign_payload
from .sign import verify as verify_payload

Signer = Callable[[bytes], Signature]
Verifier = Callable[[bytes, Signature], None]


def hash_list_for(trace: Trace, assessment: Assessment) -> HashList:
    return HashList(
        skill="sha256:" + assessment.skill_content_hash,
        trace=trace.hash,
        sandbox=trace.sandbox_config_hashes,
    )


def bundle_payload(
    hash_list: HashList,
    skill_source: SkillSource,
    trace: Trace,
    assessment: Assessment,
) -> dict[str, object]:
    return {
        "schema": trace.schema,
        "hash_list": hash_list.to_payload(),
        "skill": skill_source.to_payload(),
        "trace": trace.to_payload(),
        "assessment": assessment.to_payload(),
    }


def create_bundle(
    skill: Skill, source: str, trace: Trace, strictness: Strictness, signer: Signer
) -> Bundle:
    skill_source = _skill_source(skill, source)
    try:
        assessment = assess(skill, trace, policy=StrictnessPolicy(level=strictness))
    except CaptureError as exc:
        raise BundleError(f"skill-mismatch: {exc}") from None
    hashes = hash_list_for(trace, assessment)
    payload = bundle_payload(hashes, skill_source, trace, assessment)
    signature = signer(canonical(payload).encode("utf-8"))
    if not isinstance(signature, Signature):
        raise BundleError(f"signer must return a Signature, got {signature!r}")
    return Bundle(
        skill=skill_source,
        hash_list=hashes,
        trace=trace,
        assessment=assessment,
        signature=signature,
    )


def _skill_source(skill: Skill, source: str) -> SkillSource:
    if not isinstance(source, str):
        raise BundleError(f"skill-mismatch: source must be text, got {source!r}")
    try:
        digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
    except UnicodeEncodeError as exc:
        raise BundleError(f"skill-mismatch: source is not valid UTF-8: {exc}") from None
    if digest != skill.content_hash:
        raise BundleError("skill-mismatch: source does not match the parsed skill")
    hint = skill.format if skill.format is Format.CURSOR else None
    return SkillSource("sha256:" + digest, source, hint)


def verify_bundle(bundle: Bundle, verifier: Verifier) -> None:
    verifier(bundle.unsigned_json().encode("utf-8"), bundle.signature)


def build(
    skill: Skill, source: str, trace: Trace, strictness: Strictness, private_key: Path
) -> Bundle:
    return create_bundle(
        skill,
        source,
        trace,
        strictness,
        lambda data: sign_payload(data, private_key),
    )


def replay(bundle: Bundle) -> Assessment:
    skill_format = bundle.skill.format
    path = (
        Path(f"{bundle.trace.skill_name}.mdc")
        if skill_format is Format.CURSOR
        else Path("SKILL.md")
    )
    try:
        skill = parse_skill_text(bundle.skill.source, path, format=skill_format)
    except SkillParseError as exc:
        raise BundleError(
            f"replay-mismatch: stored skill does not parse: {exc.detail}"
        ) from None
    if skill.content_hash != bundle.trace.skill_content_hash:
        raise BundleError(
            "replay-mismatch: stored skill does not match the trace: "
            f"{skill.content_hash} != {bundle.trace.skill_content_hash}"
        )
    try:
        assessment = assess(
            skill,
            bundle.trace,
            policy=StrictnessPolicy(level=bundle.assessment.strictness),
        )
    except (CaptureError, VerdictError) as exc:
        raise BundleError(f"replay-mismatch: {exc}") from None
    if assessment != bundle.assessment:
        raise BundleError(
            "replay-mismatch: the stored assessment does not follow from the trace and skill"
        )
    return assessment


def verify(bundle: Bundle, public_key: Path) -> None:
    verify_bundle(
        bundle,
        lambda data, signature: verify_payload(data, signature, public_key),
    )
    replay(bundle)
