"""Build one assessed run into a bundle and check its signature, around an injectable signer."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from assay.canonical import canonical
from assay.capture import CaptureError, Trace
from assay.ingest import Skill
from assay.verdict import Assessment, Strictness, StrictnessPolicy, assess

from .records import BUNDLE_SCHEMA, Bundle, BundleError, HashList, Signature
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
    hash_list: HashList, trace: Trace, assessment: Assessment
) -> dict[str, object]:
    return {
        "schema": BUNDLE_SCHEMA,
        "hash_list": hash_list.to_payload(),
        "trace": trace.to_payload(),
        "assessment": assessment.to_payload(),
    }


def create_bundle(
    skill: Skill, trace: Trace, strictness: Strictness, signer: Signer
) -> Bundle:
    try:
        assessment = assess(skill, trace, policy=StrictnessPolicy(level=strictness))
    except CaptureError as exc:
        raise BundleError(f"skill-mismatch: {exc}") from None
    hashes = hash_list_for(trace, assessment)
    payload = bundle_payload(hashes, trace, assessment)
    signature = signer(canonical(payload).encode("utf-8"))
    if not isinstance(signature, Signature):
        raise BundleError(f"signer must return a Signature, got {signature!r}")
    return Bundle(
        hash_list=hashes,
        trace=trace,
        assessment=assessment,
        signature=signature,
    )


def verify_bundle(bundle: Bundle, verifier: Verifier) -> None:
    verifier(bundle.unsigned_json().encode("utf-8"), bundle.signature)


def build(
    skill: Skill, trace: Trace, strictness: Strictness, private_key: Path
) -> Bundle:
    return create_bundle(
        skill,
        trace,
        strictness,
        lambda data: sign_payload(data, private_key),
    )


def verify(bundle: Bundle, public_key: Path) -> None:
    verify_bundle(
        bundle,
        lambda data, signature: verify_payload(data, signature, public_key),
    )
