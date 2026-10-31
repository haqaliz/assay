import json
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
        sandbox_config_hashes=(),
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
        ({"schema": 1}, "schema"),
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
        == "4b47ea94dde0e048bed381d64028b39d4858b5d84e5bb957c1f1a1ac02ebbea8"
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


def test_event_requires_typed_kind_outcome_and_string_target():
    with pytest.raises(ValueError, match="kind"):
        Event(kind="file-read", outcome=EventOutcome.OK, target="x",
              content_sha256="a" * 64, content_bytes=0, excerpt="")
    with pytest.raises(ValueError, match="outcome"):
        Event(kind=EventKind.FILE_READ, outcome="ok", target="x",
              content_sha256="a" * 64, content_bytes=0, excerpt="")
    with pytest.raises(ValueError, match="target"):
        Event(kind=EventKind.FILE_READ, outcome=EventOutcome.OK, target=None,
              content_sha256="a" * 64, content_bytes=0, excerpt="")
    with pytest.raises(ValueError, match="excerpt"):
        Event(kind=EventKind.FILE_READ, outcome=EventOutcome.OK, target="x",
              content_sha256="a" * 64, content_bytes=0, excerpt=None)


def test_trace_schema_must_be_the_int_two():
    with pytest.raises(ValueError, match="schema"):
        Trace(skill_name="demo", skill_content_hash="a" * 64, task_sha256="b" * 64,
              cause=None, input_tokens=0, output_tokens=0, cost_usd=0.0,
              events=(), schema=1.0, sandbox_config_hashes=())


def test_trace_schema_2_requires_sandbox_config_hashes():
    with pytest.raises(TypeError):
        Trace(skill_name="demo", skill_content_hash="a" * 64, task_sha256="b" * 64,
              cause=None, input_tokens=0, output_tokens=0, cost_usd=0.0, events=())
    with pytest.raises(ValueError, match="schema"):
        trace(schema=1)


def test_sandbox_config_hashes_are_sorted_and_unique():
    a = "sha256:" + "a" * 64
    b = "sha256:" + "b" * 64
    assert trace(sandbox_config_hashes=(b, a, b)).sandbox_config_hashes == (a, b)
    assert trace(sandbox_config_hashes=[b, a]).sandbox_config_hashes == (a, b)


@pytest.mark.parametrize(
    "value",
    [
        "a" * 64,
        "md5:" + "a" * 64,
        "sha256:" + "a" * 63,
        "sha256:" + "A" * 64,
        "sha256:" + "g" * 64,
    ],
)
def test_sandbox_config_hash_must_be_prefixed_sha256(value):
    with pytest.raises(ValueError, match="sandbox config hash"):
        trace(sandbox_config_hashes=(value,))


def test_trace_payload_carries_sandbox_config_hashes():
    a = "sha256:" + "a" * 64
    b = "sha256:" + "b" * 64
    original = trace(sandbox_config_hashes=(b, a))
    assert original.to_payload()["sandbox_config_hashes"] == [a, b]
    assert trace().to_payload()["sandbox_config_hashes"] == []
    assert Trace.from_json(original.to_json()).sandbox_config_hashes == (a, b)


def test_schema_1_trace_json_is_refused_by_name():
    payload = json.loads(trace().to_json())
    payload["schema"] = 1
    with pytest.raises(CaptureError, match="schema"):
        Trace.from_json(json.dumps(payload))


def test_from_json_rejects_a_null_target_as_a_capture_error():
    payload = json.loads(trace().to_json())
    payload["events"] = [
        {
            "kind": "file-read",
            "outcome": "ok",
            "target": None,
            "input_sha256": None,
            "request": None,
            "content_sha256": "a" * 64,
            "content_bytes": 0,
            "excerpt": "",
            "denials": [],
            "truncated": False,
        }
    ]
    with pytest.raises(CaptureError):
        Trace.from_json(json.dumps(payload))


def test_from_json_rejects_a_string_where_denials_must_be_a_list():
    payload = json.loads(trace().to_json())
    payload["events"] = [
        {
            "kind": "shell",
            "outcome": "ok",
            "target": "true",
            "input_sha256": None,
            "request": None,
            "content_sha256": "a" * 64,
            "content_bytes": 0,
            "excerpt": "",
            "denials": "network: x",
            "truncated": False,
        }
    ]
    with pytest.raises(CaptureError):
        Trace.from_json(json.dumps(payload))


def test_request_and_truncated_round_trip():
    event = Event(
        kind=EventKind.NETWORK,
        outcome=EventOutcome.OK,
        target="api.example.com:443",
        request="https://api.example.com/collect?secret=x",
        content_sha256="a" * 64,
        content_bytes=12,
        excerpt="body",
        truncated=True,
    )
    loaded = Trace.from_json(Trace(skill_name="demo", skill_content_hash="a" * 64,
                                   task_sha256="b" * 64, cause=None, input_tokens=0,
                                   output_tokens=0, cost_usd=0.0, events=(event,),
                                   sandbox_config_hashes=()).to_json())
    assert loaded.events[0].request == event.request
    assert loaded.events[0].truncated is True
