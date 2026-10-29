from pathlib import Path

import pytest

from assay.agent import RunOutcome, Usage
from assay.capture import (
    CaptureError,
    Event,
    EventKind,
    EventOutcome,
    Trace,
    TraceIntegrityError,
    TraceStore,
    capture,
    diff,
)
from assay.ingest import Scope, Skill


def skill(**over):
    base = dict(
        name="demo",
        description="does a demo",
        scope=Scope(files=("out/*",)),
        body="BODY\n",
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
        input_tokens=1,
        output_tokens=2,
        cost_usd=0.0,
        events=(
            Event(
                kind=EventKind.FILE_READ,
                outcome=EventOutcome.OK,
                target="out/x.txt",
                content_sha256="c" * 64,
                content_bytes=0,
                excerpt="",
            ),
        ),
    )
    base.update(over)
    return Trace(**base)


def test_save_creates_the_root_and_names_the_file_by_hash(tmp_path):
    root = tmp_path / "traces"
    store = TraceStore(root)
    original = trace()

    path = store.save(original)

    assert root.is_dir()
    assert path == root / f"{original.hash}.json"
    assert path.read_text(encoding="utf-8") == original.to_json()
    assert [entry.name for entry in root.iterdir()] == [path.name]


def test_load_round_trips_a_saved_trace(tmp_path):
    store = TraceStore(tmp_path)
    original = trace()

    assert store.load(store.save(original)) == original


def test_load_rejects_an_edited_file(tmp_path):
    store = TraceStore(tmp_path)
    path = store.save(trace())
    path.write_text(path.read_text(encoding="utf-8").replace("demo", "evil"))

    with pytest.raises(TraceIntegrityError, match="hash"):
        store.load(path)


def test_load_rejects_a_file_whose_name_is_not_its_hash(tmp_path):
    store = TraceStore(tmp_path)
    path = store.save(trace())
    renamed = path.with_name("0" * 64 + ".json")
    path.rename(renamed)

    with pytest.raises(TraceIntegrityError, match="hash"):
        store.load(renamed)


def test_load_rejects_the_right_hash_under_the_wrong_suffix(tmp_path):
    store = TraceStore(tmp_path)
    path = store.save(trace())
    renamed = path.with_suffix(".txt")
    path.rename(renamed)

    with pytest.raises(TraceIntegrityError, match="filename"):
        store.load(renamed)


def test_load_rejects_invalid_json_as_a_capture_error(tmp_path):
    invalid = tmp_path / "invalid.json"
    invalid.write_text("not json", encoding="utf-8")

    with pytest.raises(CaptureError):
        TraceStore(tmp_path).load(invalid)


def test_capture_save_load_diff_round_trip(tmp_path):
    declared = skill()
    outcome = RunOutcome(
        cause=None,
        final_text="done",
        steps=1,
        actions=(),
        usage=Usage(input_tokens=3, output_tokens=4),
        cost_usd=0.002,
    )
    original = capture(declared, "do it", outcome)
    store = TraceStore(tmp_path)

    loaded = store.load(store.save(original))

    assert loaded == original
    assert diff(declared, loaded) == diff(declared, original)
