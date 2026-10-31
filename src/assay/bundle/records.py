"""The signed attestation bundle: one canonical record of one assessed run."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from assay.canonical import canonical
from assay.capture import CaptureError, Trace
from assay.verdict import Assessment, VerdictError

BUNDLE_SCHEMA = 1
NAMESPACE = "assay"

_SKILL_HASH = re.compile(r"sha256:[0-9a-f]{64}")
_TRACE_HASH = re.compile(r"[0-9a-f]{64}")
_SIGNER = re.compile(r"SHA256:[A-Za-z0-9+/]+")
_BEGIN = "-----BEGIN SSH SIGNATURE-----"
_END = "-----END SSH SIGNATURE-----"
_TOP_LEVEL = frozenset({"schema", "hash_list", "trace", "assessment", "signature"})
_HASH_LIST = frozenset({"skill", "trace", "sandbox"})
_SIGNATURE = frozenset({"namespace", "signer", "value"})


class BundleError(ValueError):
    """A bundle could not be built, encoded, loaded or verified."""


def _matches(pattern: re.Pattern[str], value: object) -> bool:
    return isinstance(value, str) and pattern.fullmatch(value) is not None


@dataclass(frozen=True, slots=True)
class HashList:
    skill: str
    trace: str
    sandbox: tuple[str, ...]

    def __post_init__(self) -> None:
        if not _matches(_SKILL_HASH, self.skill):
            raise BundleError(
                f"skill must be 'sha256:' with 64 lowercase hex characters, got {self.skill!r}"
            )
        if not _matches(_TRACE_HASH, self.trace):
            raise BundleError(
                f"trace must be 64 lowercase hex characters, got {self.trace!r}"
            )
        if isinstance(self.sandbox, str) or not isinstance(
            self.sandbox, (list, tuple, set, frozenset)
        ):
            raise BundleError(
                f"sandbox must be a collection of hashes, got {self.sandbox!r}"
            )
        hashes = tuple(self.sandbox)
        for value in hashes:
            if not _matches(_SKILL_HASH, value):
                raise BundleError(
                    "sandbox entry must be 'sha256:' with 64 lowercase hex "
                    f"characters, got {value!r}"
                )
        object.__setattr__(self, "sandbox", tuple(sorted(set(hashes))))

    def to_payload(self) -> dict[str, object]:
        return {
            "skill": self.skill,
            "trace": self.trace,
            "sandbox": list(self.sandbox),
        }


@dataclass(frozen=True, slots=True)
class Signature:
    signer: str
    value: str
    namespace: str = NAMESPACE

    def __post_init__(self) -> None:
        if self.namespace != NAMESPACE:
            raise BundleError(f"namespace must be {NAMESPACE!r}, got {self.namespace!r}")
        if not _matches(_SIGNER, self.signer):
            raise BundleError(
                "signer must be 'SHA256:' with base64 characters, "
                f"got {self.signer!r}"
            )
        if (
            not isinstance(self.value, str)
            or not self.value.startswith(_BEGIN)
            or not self.value.rstrip("\n").endswith(_END)
        ):
            raise BundleError(f"value must be an armored SSH signature, got {self.value!r}")

    def to_payload(self) -> dict[str, object]:
        return {
            "namespace": self.namespace,
            "signer": self.signer,
            "value": self.value,
        }


@dataclass(frozen=True, slots=True)
class Bundle:
    hash_list: HashList
    trace: Trace
    assessment: Assessment
    signature: Signature
    schema: int = BUNDLE_SCHEMA

    def __post_init__(self) -> None:
        if not isinstance(self.hash_list, HashList):
            raise BundleError(f"hash_list must be a HashList, got {self.hash_list!r}")
        if not isinstance(self.trace, Trace):
            raise BundleError(f"trace must be a Trace, got {self.trace!r}")
        if not isinstance(self.assessment, Assessment):
            raise BundleError(
                f"assessment must be an Assessment, got {self.assessment!r}"
            )
        if not isinstance(self.signature, Signature):
            raise BundleError(
                f"signature must be a Signature, got {self.signature!r}"
            )
        if (
            isinstance(self.schema, bool)
            or not isinstance(self.schema, int)
            or self.schema != BUNDLE_SCHEMA
        ):
            raise BundleError(
                f"schema must be the int {BUNDLE_SCHEMA}, got {self.schema!r}"
            )
        skills = {
            "hash_list": self.hash_list.skill,
            "trace": "sha256:" + self.trace.skill_content_hash,
            "assessment": "sha256:" + self.assessment.skill_content_hash,
        }
        if len(set(skills.values())) != 1:
            raise BundleError(f"hash-mismatch: skill {skills}")
        if (
            self.hash_list.trace != self.trace.hash
            or self.hash_list.trace != self.assessment.trace_hash
        ):
            raise BundleError(
                f"hash-mismatch: trace {self.hash_list.trace!r} != "
                f"trace {self.trace.hash!r} / assessment {self.assessment.trace_hash!r}"
            )
        if self.hash_list.sandbox != self.trace.sandbox_config_hashes:
            raise BundleError(
                f"hash-mismatch: sandbox {self.hash_list.sandbox!r} != "
                f"trace {self.trace.sandbox_config_hashes!r}"
            )

    def to_payload(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "hash_list": self.hash_list.to_payload(),
            "trace": self.trace.to_payload(),
            "assessment": self.assessment.to_payload(),
            "signature": self.signature.to_payload(),
        }

    def unsigned_payload(self) -> dict[str, object]:
        payload = self.to_payload()
        del payload["signature"]
        return payload

    def to_json(self) -> str:
        return canonical(self.to_payload())

    def unsigned_json(self) -> str:
        return canonical(self.unsigned_payload())

    @classmethod
    def from_json(cls, text: str) -> Bundle:
        try:
            payload = json.loads(text)
        except (UnicodeError, TypeError, RecursionError, json.JSONDecodeError) as exc:
            raise BundleError(f"bundle-invalid: {exc}") from None
        if not isinstance(payload, dict):
            raise BundleError("bundle-invalid: bundle JSON must be an object")
        if set(payload) != _TOP_LEVEL:
            raise BundleError(
                f"bundle-invalid: top-level keys must be {sorted(_TOP_LEVEL)}, "
                f"got {sorted(payload)}"
            )
        hash_list = payload["hash_list"]
        if not isinstance(hash_list, dict) or set(hash_list) != _HASH_LIST:
            raise BundleError(
                f"bundle-invalid: hash_list keys must be {sorted(_HASH_LIST)}, "
                f"got {sorted(hash_list) if isinstance(hash_list, dict) else hash_list!r}"
            )
        signature = payload["signature"]
        if not isinstance(signature, dict) or set(signature) != _SIGNATURE:
            raise BundleError(
                f"bundle-invalid: signature keys must be {sorted(_SIGNATURE)}, "
                f"got {sorted(signature) if isinstance(signature, dict) else signature!r}"
            )
        schema = payload["schema"]
        if (
            isinstance(schema, bool)
            or not isinstance(schema, int)
            or schema != BUNDLE_SCHEMA
        ):
            raise BundleError(
                f"bundle-invalid: schema must be the int {BUNDLE_SCHEMA}, got {schema!r}"
            )
        try:
            trace = Trace.from_json(canonical(payload["trace"]))
        except (CaptureError, TypeError, ValueError, RecursionError) as exc:
            raise BundleError(f"bundle-invalid: {exc}") from None
        try:
            assessment = Assessment.from_payload(payload["assessment"])
        except VerdictError as exc:
            raise BundleError(f"bundle-invalid: {exc}") from None
        try:
            hashes = HashList(
                skill=hash_list["skill"],
                trace=hash_list["trace"],
                sandbox=hash_list["sandbox"],
            )
            sig = Signature(
                signer=signature["signer"],
                value=signature["value"],
                namespace=signature["namespace"],
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise BundleError(f"bundle-invalid: {exc}") from None
        record = cls(
            hash_list=hashes,
            trace=trace,
            assessment=assessment,
            signature=sig,
            schema=schema,
        )
        if record.to_json() != text:
            raise BundleError("bundle-not-canonical: bundle is not the canonical encoding")
        return record
