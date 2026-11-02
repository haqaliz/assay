"""Labeled corpus cases: validated inputs to the offline verdict benchmark."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from pathlib import Path

from assay.capture import CaptureError, Trace, TraceStore
from assay.ingest import Skill, SkillParseError, parse_skill
from assay.verdict import FindingClass, Strictness

CASE_KEYS = frozenset(
    {
        "schema",
        "id",
        "label",
        "labeler",
        "labeled_at",
        "rationale",
        "source",
        "strictness",
        "trace",
        "expected_classes",
    }
)
_ID = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
_TRACE = re.compile(r"[0-9a-f]{64}\.json")


class Label(StrEnum):
    MALICIOUS = "malicious"
    CLEAN = "clean"


class Source(StrEnum):
    SYNTHETIC = "synthetic"
    LOCAL_MODEL = "local-model"


class CaseError(ValueError):
    """A corpus or one of its cases could not be validated."""


@dataclass(frozen=True, slots=True)
class Case:
    id: str
    label: Label
    labeler: str
    labeled_at: date
    rationale: str
    source: Source
    strictness: Strictness
    skill: Skill
    trace: Trace
    expected_classes: tuple[FindingClass, ...]
    path: Path

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or _ID.fullmatch(self.id) is None:
            raise CaseError(f"id must be kebab-case, got {self.id!r}")
        if not isinstance(self.label, Label):
            raise CaseError(f"label must be a Label, got {self.label!r}")
        if not isinstance(self.labeler, str) or not self.labeler.strip():
            raise CaseError(f"labeler must be a non-empty string, got {self.labeler!r}")
        if not isinstance(self.labeled_at, date):
            raise CaseError(f"labeled_at must be a date, got {self.labeled_at!r}")
        if not isinstance(self.rationale, str) or not self.rationale.strip():
            raise CaseError(f"rationale must be a non-empty string, got {self.rationale!r}")
        if not isinstance(self.source, Source):
            raise CaseError(f"source must be a Source, got {self.source!r}")
        if not isinstance(self.strictness, Strictness):
            raise CaseError(f"strictness must be a Strictness, got {self.strictness!r}")
        if not isinstance(self.skill, Skill):
            raise CaseError(f"skill must be a Skill, got {self.skill!r}")
        if not isinstance(self.trace, Trace):
            raise CaseError(f"trace must be a Trace, got {self.trace!r}")
        classes = tuple(self.expected_classes)
        if not all(isinstance(class_, FindingClass) for class_ in classes):
            raise CaseError("expected_classes must be FindingClass values")
        object.__setattr__(self, "expected_classes", classes)
        if self.trace.skill_content_hash != self.skill.content_hash:
            raise CaseError(
                f"skill hash mismatch: trace {self.trace.skill_content_hash} != "
                f"skill {self.skill.content_hash}"
            )


def load_case(directory: Path) -> Case:
    directory = Path(directory)
    case_id = directory.name
    try:
        payload = _payload(directory)
        return _case(directory, payload)
    except CaseError as exc:
        detail = str(exc)
        if detail.startswith("case-invalid:"):
            raise
        raise CaseError(f"case-invalid: {case_id}: {detail}") from None
    except (
        CaptureError,
        KeyError,
        OSError,
        RecursionError,
        SkillParseError,
        TypeError,
        ValueError,
    ) as exc:
        raise CaseError(f"case-invalid: {case_id}: {exc}") from None


def load_corpus(root: Path) -> tuple[Case, ...]:
    root = Path(root)
    # A repo corpus keeps cases under cases/; a flat directory is also accepted.
    container = root / "cases"
    scan = container if container.is_dir() else root
    try:
        entries = sorted(scan.iterdir(), key=lambda entry: entry.name)
    except OSError as exc:
        raise CaseError(f"corpus-unreadable: {root}: {exc}") from None
    directories = [entry for entry in entries if entry.is_dir()]
    if not directories:
        raise CaseError(f"corpus-empty: {root}: no case directories")
    cases: list[Case] = []
    seen: set[str] = set()
    for directory in directories:
        case = load_case(directory)
        if case.id in seen:
            raise CaseError(f"case-invalid: {case.id}: duplicate id")
        seen.add(case.id)
        cases.append(case)
    return tuple(cases)


def _payload(directory: Path) -> dict[str, object]:
    try:
        text = (directory / "case.json").read_text(encoding="utf-8")
    except OSError as exc:
        raise CaseError(f"cannot read case.json: {exc}") from None
    try:
        payload = json.loads(text)
    except (RecursionError, ValueError) as exc:
        raise CaseError(f"case.json is not valid JSON: {exc}") from None
    if not isinstance(payload, dict):
        raise CaseError("case.json must be an object")
    return payload


def _case(directory: Path, payload: dict[str, object]) -> Case:
    keys = set(payload)
    if keys != CASE_KEYS:
        missing = sorted(CASE_KEYS - keys)
        unknown = sorted(keys - CASE_KEYS)
        raise CaseError(
            f"case.json keys must be exactly {sorted(CASE_KEYS)}, "
            f"missing {missing}, unknown {unknown}"
        )
    schema = payload["schema"]
    if isinstance(schema, bool) or not isinstance(schema, int) or schema != 1:
        raise CaseError(f"schema must be the int 1, got {schema!r}")
    case_id = _text(payload, "id")
    if _ID.fullmatch(case_id) is None:
        raise CaseError(f"id must be kebab-case, got {case_id!r}")
    if case_id != directory.name:
        raise CaseError(
            f"id must equal the directory name {directory.name!r}, got {case_id!r}"
        )
    label = _enum(Label, payload["label"], "label")
    source = _enum(Source, payload["source"], "source")
    strictness = _enum(Strictness, payload["strictness"], "strictness")
    labeled_at = _date(payload["labeled_at"])
    labeler = _text(payload, "labeler")
    rationale = _text(payload, "rationale")
    trace_name = payload["trace"]
    if not isinstance(trace_name, str) or _TRACE.fullmatch(trace_name) is None:
        raise CaseError(
            "trace must be a bare '<64 lowercase hex>.json' filename, "
            f"got {trace_name!r}"
        )
    trace_path = directory / trace_name
    if not trace_path.is_file():
        raise CaseError(f"trace does not exist in the case directory: {trace_name}")
    expected_classes = _classes(payload["expected_classes"])
    skill = parse_skill(directory / "SKILL.md")
    trace = TraceStore(directory).load(trace_path)
    return Case(
        id=case_id,
        label=label,
        labeler=labeler,
        labeled_at=labeled_at,
        rationale=rationale,
        source=source,
        strictness=strictness,
        skill=skill,
        trace=trace,
        expected_classes=expected_classes,
        path=directory,
    )


def _text(payload: dict[str, object], field: str) -> str:
    value = payload[field]
    if not isinstance(value, str) or not value.strip():
        raise CaseError(f"{field} must be a non-empty string, got {value!r}")
    return value


def _enum(enum: type[StrEnum], value: object, field: str) -> StrEnum:
    try:
        return enum(value)
    except (TypeError, ValueError):
        allowed = ", ".join(member.value for member in enum)
        raise CaseError(f"{field} must be one of {allowed}, got {value!r}") from None


def _date(value: object) -> date:
    if not isinstance(value, str):
        raise CaseError(f"labeled_at must be a YYYY-MM-DD string, got {value!r}")
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        raise CaseError(f"labeled_at must be a date, got {value!r}") from None
    if parsed.isoformat() != value:
        raise CaseError(f"labeled_at must be a canonical YYYY-MM-DD date, got {value!r}")
    return parsed


def _classes(value: object) -> tuple[FindingClass, ...]:
    if not isinstance(value, list):
        raise CaseError(f"expected_classes must be a list, got {value!r}")
    classes: list[FindingClass] = []
    for item in value:
        try:
            classes.append(FindingClass(item))
        except (TypeError, ValueError):
            raise CaseError(
                f"expected_classes must contain FindingClass values, got {item!r}"
            ) from None
    if len(set(classes)) != len(classes):
        raise CaseError("expected_classes must not contain duplicates")
    return tuple(classes)
