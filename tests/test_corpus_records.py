import hashlib
import json
from dataclasses import FrozenInstanceError
from datetime import date
from pathlib import Path

import pytest

from assay.capture import Event, EventKind, EventOutcome, Trace, TraceStore
from assay.corpus import Case, CaseError, Label, Source, load_case, load_corpus
from assay.ingest import parse_skill
from assay.verdict import FindingClass, Strictness

SKILL_TEXT = """---
name: demo
description: A demo skill.
allowed-tools: Read
metadata:
  assay:
    files:
      - in.txt
    network: []
---
Do the demo.
"""


def event(
    kind=EventKind.FILE_READ,
    target="in.txt",
    **over,
):
    base = dict(
        kind=kind,
        outcome=EventOutcome.OK,
        target=target,
        content_sha256="d" * 64,
        content_bytes=2,
        excerpt="hi",
    )
    base.update(over)
    return Event(**base)


def make_case(
    tmp_path: Path,
    *,
    directory_name: str = "demo-case",
    skill_text: str = SKILL_TEXT,
    events=None,
    trace_skill_hash: str | None = None,
    **over,
) -> Path:
    directory = tmp_path / directory_name
    directory.mkdir()
    (directory / "SKILL.md").write_text(skill_text, encoding="utf-8")
    skill = parse_skill(directory / "SKILL.md")
    trace = Trace(
        skill_name=skill.name,
        skill_content_hash=trace_skill_hash or skill.content_hash,
        task_sha256="b" * 64,
        cause=None,
        input_tokens=0,
        output_tokens=0,
        cost_usd=0.0,
        events=(event(),) if events is None else events,
        sandbox_config_hashes=(),
    )
    saved = TraceStore(directory).save(trace)
    payload = {
        "schema": 1,
        "id": directory_name,
        "label": "malicious",
        "labeler": "aliz",
        "labeled_at": "2026-11-03",
        "rationale": "It does something harmful.",
        "source": "synthetic",
        "strictness": "standard",
        "trace": saved.name,
        "expected_classes": ["shell"],
    }
    payload.update(over)
    (directory / "case.json").write_text(json.dumps(payload), encoding="utf-8")
    return directory


def read_payload(directory: Path) -> dict:
    return json.loads((directory / "case.json").read_text(encoding="utf-8"))


def write_payload(directory: Path, payload: dict) -> None:
    (directory / "case.json").write_text(json.dumps(payload), encoding="utf-8")


def rewrite_trace(directory: Path, text: str) -> None:
    payload = read_payload(directory)
    (directory / payload["trace"]).unlink()
    digest = hashlib.sha256(text.encode()).hexdigest()
    path = directory / f"{digest}.json"
    path.write_text(text, encoding="utf-8")
    write_payload(directory, {**payload, "trace": path.name})


def test_enums_are_the_closed_sets():
    assert {label.value for label in Label} == {"malicious", "clean"}
    assert {source.value for source in Source} == {"synthetic", "local-model"}
    assert issubclass(CaseError, ValueError)


def test_load_case_returns_a_validated_frozen_case(tmp_path):
    directory = make_case(tmp_path)

    case = load_case(directory)

    assert isinstance(case, Case)
    assert case.id == "demo-case"
    assert case.label is Label.MALICIOUS
    assert case.labeler == "aliz"
    assert case.labeled_at == date(2026, 11, 3)
    assert case.rationale == "It does something harmful."
    assert case.source is Source.SYNTHETIC
    assert case.strictness is Strictness.STANDARD
    assert case.expected_classes == (FindingClass.SHELL,)
    assert case.path == directory
    assert case.skill.source_path == directory / "SKILL.md"
    assert case.trace.skill_content_hash == case.skill.content_hash
    with pytest.raises(FrozenInstanceError):
        case.label = Label.CLEAN


def test_expected_classes_may_be_empty(tmp_path):
    case = load_case(make_case(tmp_path, expected_classes=[]))

    assert case.expected_classes == ()


def test_case_json_refuses_an_unknown_key(tmp_path):
    directory = make_case(tmp_path, extra="nope")

    with pytest.raises(CaseError, match=r"^case-invalid: demo-case: "):
        load_case(directory)


def test_case_json_refuses_a_missing_key(tmp_path):
    directory = make_case(tmp_path)
    payload = read_payload(directory)
    del payload["rationale"]
    write_payload(directory, payload)

    with pytest.raises(CaseError, match=r"^case-invalid: demo-case: "):
        load_case(directory)


@pytest.mark.parametrize("schema", [2, True, "1", None])
def test_schema_must_be_the_int_one(tmp_path, schema):
    directory = make_case(tmp_path, schema=schema)

    with pytest.raises(CaseError, match="schema"):
        load_case(directory)


@pytest.mark.parametrize(
    "field, value",
    [
        ("label", "evil"),
        ("label", 1),
        ("source", "remote"),
        ("source", None),
        ("strictness", "loose"),
        ("strictness", False),
    ],
)
def test_label_source_and_strictness_are_closed_enums(tmp_path, field, value):
    directory = make_case(tmp_path, **{field: value})

    with pytest.raises(CaseError, match=field):
        load_case(directory)


@pytest.mark.parametrize(
    "raw",
    ["2026-02-30", "2026-1-1", "2026-11-03T00:00:00", "03/11/2026", 20261103],
)
def test_labeled_at_must_be_a_real_canonical_date(tmp_path, raw):
    directory = make_case(tmp_path, labeled_at=raw)

    with pytest.raises(CaseError, match="labeled_at"):
        load_case(directory)


@pytest.mark.parametrize("field", ["labeler", "rationale"])
@pytest.mark.parametrize("value", ["", "   ", None])
def test_labeler_and_rationale_must_be_non_empty_strings(tmp_path, field, value):
    directory = make_case(tmp_path, **{field: value})

    with pytest.raises(CaseError, match=field):
        load_case(directory)


@pytest.mark.parametrize("case_id", ["Demo_Case", "demo--case", "-demo", "demo-"])
def test_id_must_be_kebab_case(tmp_path, case_id):
    directory = make_case(tmp_path, id=case_id)

    with pytest.raises(CaseError, match="id"):
        load_case(directory)


def test_id_must_equal_the_directory_name(tmp_path):
    directory = make_case(tmp_path, id="other-case")

    with pytest.raises(CaseError, match="directory"):
        load_case(directory)


def test_a_missing_case_json_is_case_invalid(tmp_path):
    directory = make_case(tmp_path)
    (directory / "case.json").unlink()

    with pytest.raises(CaseError, match=r"^case-invalid: demo-case: "):
        load_case(directory)


def test_a_missing_directory_is_case_invalid(tmp_path):
    with pytest.raises(CaseError, match=r"^case-invalid: "):
        load_case(tmp_path / "missing")


@pytest.mark.parametrize("text", ["{", "[]", "null"])
def test_case_json_must_be_a_json_object(tmp_path, text):
    directory = make_case(tmp_path)
    (directory / "case.json").write_text(text, encoding="utf-8")

    with pytest.raises(CaseError, match=r"^case-invalid: demo-case: "):
        load_case(directory)


def test_a_missing_skill_md_is_case_invalid(tmp_path):
    directory = make_case(tmp_path)
    (directory / "SKILL.md").unlink()

    with pytest.raises(CaseError, match=r"^case-invalid: demo-case: "):
        load_case(directory)


def test_a_missing_trace_is_case_invalid(tmp_path):
    directory = make_case(tmp_path)
    payload = read_payload(directory)
    (directory / payload["trace"]).unlink()

    with pytest.raises(CaseError, match=r"^case-invalid: demo-case: "):
        load_case(directory)


@pytest.mark.parametrize(
    "trace_name",
    [
        "../" + "0" * 64 + ".json",
        "/" + "0" * 64 + ".json",
        "0" * 63 + ".json",
        "0" * 65 + ".json",
        "A" * 64 + ".json",
        "trace.json",
        1,
        None,
    ],
)
def test_trace_must_be_a_bare_lowercase_hex_filename(tmp_path, trace_name):
    directory = make_case(tmp_path, trace=trace_name)

    with pytest.raises(CaseError, match="trace"):
        load_case(directory)


def test_a_trace_filename_that_is_not_its_hash_is_refused(tmp_path):
    directory = make_case(tmp_path)
    payload = read_payload(directory)
    saved = directory / payload["trace"]
    renamed = saved.with_name("0" * 64 + ".json")
    saved.rename(renamed)
    write_payload(directory, {**payload, "trace": renamed.name})

    with pytest.raises(CaseError, match="hash"):
        load_case(directory)


def test_a_non_canonical_trace_is_refused(tmp_path):
    directory = make_case(tmp_path)
    payload = read_payload(directory)
    text = (directory / payload["trace"]).read_text(encoding="utf-8")
    rewrite_trace(directory, text.replace(",", ", ", 1))

    with pytest.raises(CaseError, match="canonical"):
        load_case(directory)


def test_a_schema_one_trace_is_refused(tmp_path):
    directory = make_case(tmp_path)
    payload = read_payload(directory)
    trace_payload = json.loads((directory / payload["trace"]).read_text(encoding="utf-8"))
    trace_payload["schema"] = 1
    rewrite_trace(
        directory,
        json.dumps(trace_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False),
    )

    with pytest.raises(CaseError, match="schema"):
        load_case(directory)


def test_the_trace_must_belong_to_the_parsed_skill(tmp_path):
    directory = make_case(tmp_path, trace_skill_hash="c" * 64)

    with pytest.raises(CaseError, match="skill hash"):
        load_case(directory)


@pytest.mark.parametrize("value", ["shell", None, {"shell": True}])
def test_expected_classes_must_be_a_list(tmp_path, value):
    directory = make_case(tmp_path, expected_classes=value)

    with pytest.raises(CaseError, match="expected_classes"):
        load_case(directory)


@pytest.mark.parametrize("value", [["shell", "nope"], [1], [None]])
def test_expected_classes_must_contain_finding_classes(tmp_path, value):
    directory = make_case(tmp_path, expected_classes=value)

    with pytest.raises(CaseError, match="expected_classes"):
        load_case(directory)


def test_expected_classes_must_not_repeat(tmp_path):
    directory = make_case(tmp_path, expected_classes=["shell", "shell"])

    with pytest.raises(CaseError, match="duplicates"):
        load_case(directory)


def test_load_corpus_returns_a_tuple_sorted_by_id_and_skips_files(tmp_path):
    for name in ("z-case", "a-case", "m-case"):
        make_case(tmp_path, directory_name=name)
    (tmp_path / "notes.txt").write_text("not a case", encoding="utf-8")

    cases = load_corpus(tmp_path)

    assert isinstance(cases, tuple)
    assert [case.id for case in cases] == ["a-case", "m-case", "z-case"]


def test_load_corpus_descends_into_a_cases_container(tmp_path):
    container = tmp_path / "cases"
    container.mkdir()
    make_case(container, directory_name="inside")
    (tmp_path / "README.md").write_text("corpus notes", encoding="utf-8")

    cases = load_corpus(tmp_path)

    assert [case.id for case in cases] == ["inside"]


def test_load_corpus_refuses_an_empty_directory(tmp_path):
    (tmp_path / "notes.txt").write_text("not a case", encoding="utf-8")

    with pytest.raises(CaseError, match=r"^corpus-empty: "):
        load_corpus(tmp_path)


def test_load_corpus_refuses_a_missing_root(tmp_path):
    with pytest.raises(CaseError, match=r"^corpus-unreadable: "):
        load_corpus(tmp_path / "missing")


def test_load_corpus_refuses_a_root_that_is_not_a_directory(tmp_path):
    root = tmp_path / "corpus"
    root.write_text("not a directory", encoding="utf-8")

    with pytest.raises(CaseError, match=r"^corpus-unreadable: "):
        load_corpus(root)


def test_load_corpus_rejects_duplicate_ids(tmp_path, monkeypatch):
    first = load_case(make_case(tmp_path, directory_name="a-case"))
    (tmp_path / "b-case").mkdir()
    monkeypatch.setattr("assay.corpus.records.load_case", lambda directory: first)

    with pytest.raises(CaseError, match="duplicate"):
        load_corpus(tmp_path)
