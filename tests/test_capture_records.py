from dataclasses import FrozenInstanceError

import pytest

from assay.capture import (
    CaptureError,
    Event,
    EventKind,
    EventOutcome,
    Trace,
    TraceIntegrityError,
)


def event(**over):
    base = dict(
        kind=EventKind.FILE_READ,
        outcome=EventOutcome.OK,
        target="out/a.txt",
        content_sha256="c" * 64,
        content_bytes=5,
        excerpt="hello",
    )
    base.update(over)
    return Event(**base)


def trace(**over):
    base = dict(
        skill_name="demo",
        skill_content_hash="a" * 64,
        task_sha256="b" * 64,
        cause=None,
        input_tokens=12,
        output_tokens=3,
        cost_usd=0.0012,
        events=(event(),),
    )
    base.update(over)
    return Trace(**base)


def test_event_kinds_and_outcomes_are_the_closed_sets():
    assert {kind.value for kind in EventKind} == {
        "file-read",
        "file-write",
        "network",
        "shell",
        "instruction",
        "tool",
    }
    assert {outcome.value for outcome in EventOutcome} == {"ok", "denied", "failed"}


@pytest.mark.parametrize(
    "over, field",
    [
        ({"content_sha256": "C" * 64}, "content_sha256"),
        ({"content_sha256": "c" * 63}, "content_sha256"),
        ({"content_sha256": "c" * 65}, "content_sha256"),
        ({"input_sha256": "z" * 64}, "input_sha256"),
        ({"content_bytes": -1}, "content_bytes"),
        ({"content_bytes": True}, "content_bytes"),
        ({"denials": ("file-read: x", 1)}, "denials"),
    ],
)
def test_event_rejects_invalid_values(over, field):
    with pytest.raises(ValueError, match=field):
        event(**over)


@pytest.mark.parametrize(
    "over, field",
    [
        ({"skill_content_hash": "A" * 64}, "skill_content_hash"),
        ({"skill_content_hash": "a" * 63}, "skill_content_hash"),
        ({"task_sha256": "g" * 64}, "task_sha256"),
        ({"input_tokens": -1}, "input_tokens"),
        ({"output_tokens": True}, "output_tokens"),
        ({"cost_usd": float("nan")}, "cost_usd"),
        ({"cost_usd": float("inf")}, "cost_usd"),
        ({"cost_usd": -0.1}, "cost_usd"),
        ({"cost_usd": True}, "cost_usd"),
        ({"schema": 2}, "schema"),
        ({"events": ("not an event",)}, "events"),
    ],
)
def test_trace_rejects_invalid_values(over, field):
    with pytest.raises(ValueError, match=field):
        trace(**over)


def test_trace_round_trips_through_canonical_json():
    original = trace()
    text = original.to_json()
    assert Trace.from_json(text) == original
    assert Trace.from_json(text).to_payload() == original.to_payload()
    assert "\n" not in text
    assert ", " not in text
    assert '": ' not in text


@pytest.mark.parametrize("text", ["not json", "[]", "{}"])
def test_from_json_rejects_malformed_input_as_a_capture_error(text):
    with pytest.raises(CaptureError):
        Trace.from_json(text)


def test_capture_errors_are_named_value_errors():
    assert issubclass(CaptureError, ValueError)
    assert issubclass(TraceIntegrityError, CaptureError)


def test_golden_hash_pins_the_canonical_encoding():
    assert (
        trace().hash
        == "a15864d61d62ad4680abd8202ae7c9d1daa09bf8b03cf5ecd36f76a99eb4d57b"
    )


def test_canonical_json_keeps_unicode_unescaped():
    assert "héllo" in trace(events=(event(excerpt="héllo"),)).to_json()


def test_integer_cost_round_trips_with_the_same_hash():
    original = trace(cost_usd=0)
    assert Trace.from_json(original.to_json()) == original
    assert Trace.from_json(original.to_json()).hash == original.hash


def test_records_are_frozen():
    with pytest.raises(FrozenInstanceError):
        trace().skill_name = "other"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        event().target = "other"  # type: ignore[misc]


def test_hash_is_stable_and_changes_with_an_event():
    first = trace()
    assert first.hash == trace().hash
    assert len(first.hash) == 64
    changed = trace(events=(event(excerpt="bye"),))
    assert changed.hash != first.hash
    assert changed.hash == trace(events=(event(excerpt="bye"),)).hash
