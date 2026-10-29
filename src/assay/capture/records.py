"""Types produced by behavior capture. No verdicts live here; A5 owns those."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from enum import StrEnum

_HEX = frozenset("0123456789abcdef")


def _hash64(value: object, name: str) -> None:
    if not isinstance(value, str) or len(value) != 64 or any(c not in _HEX for c in value):
        raise ValueError(f"{name} must be 64 lowercase hex characters, got {value!r}")


def _non_negative_int(value: object, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative int, got {value!r}")


def _non_negative_float(value: object, name: str) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value < 0
    ):
        raise ValueError(f"{name} must be a finite non-negative number, got {value!r}")


class CaptureError(ValueError):
    """A trace could not be captured, encoded or loaded."""


class TraceIntegrityError(CaptureError):
    """A stored trace's content does not match its content address."""


class EventKind(StrEnum):
    FILE_READ = "file-read"
    FILE_WRITE = "file-write"
    NETWORK = "network"
    SHELL = "shell"
    INSTRUCTION = "instruction"
    TOOL = "tool"


class EventOutcome(StrEnum):
    OK = "ok"
    DENIED = "denied"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class Event:
    kind: EventKind
    outcome: EventOutcome
    target: str
    content_sha256: str
    content_bytes: int
    excerpt: str
    input_sha256: str | None = None
    denials: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _hash64(self.content_sha256, "content_sha256")
        if self.input_sha256 is not None:
            _hash64(self.input_sha256, "input_sha256")
        _non_negative_int(self.content_bytes, "content_bytes")
        denials = tuple(self.denials)
        if isinstance(self.denials, str) or not all(isinstance(d, str) for d in denials):
            raise ValueError("denials must be a collection of strings")
        object.__setattr__(self, "denials", denials)


@dataclass(frozen=True, slots=True)
class Trace:
    skill_name: str
    skill_content_hash: str
    task_sha256: str
    cause: str | None
    input_tokens: int
    output_tokens: int
    cost_usd: float
    events: tuple[Event, ...]
    schema: int = 1

    def __post_init__(self) -> None:
        _hash64(self.skill_content_hash, "skill_content_hash")
        _hash64(self.task_sha256, "task_sha256")
        _non_negative_int(self.input_tokens, "input_tokens")
        _non_negative_int(self.output_tokens, "output_tokens")
        _non_negative_float(self.cost_usd, "cost_usd")
        if isinstance(self.schema, bool) or self.schema != 1:
            raise ValueError(f"schema must be 1, got {self.schema!r}")
        events = tuple(self.events)
        if not all(isinstance(event, Event) for event in events):
            raise ValueError("events must be Event records")
        object.__setattr__(self, "events", events)
        object.__setattr__(self, "cost_usd", float(self.cost_usd))

    def to_payload(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "skill_name": self.skill_name,
            "skill_content_hash": self.skill_content_hash,
            "task_sha256": self.task_sha256,
            "cause": self.cause,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd": self.cost_usd,
            "events": [
                {
                    "kind": event.kind.value,
                    "outcome": event.outcome.value,
                    "target": event.target,
                    "input_sha256": event.input_sha256,
                    "content_sha256": event.content_sha256,
                    "content_bytes": event.content_bytes,
                    "excerpt": event.excerpt,
                    "denials": list(event.denials),
                }
                for event in self.events
            ],
        }

    def to_json(self) -> str:
        return json.dumps(
            self.to_payload(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )

    @property
    def hash(self) -> str:
        return hashlib.sha256(self.to_json().encode("utf-8")).hexdigest()

    @classmethod
    def from_json(cls, text: str) -> Trace:
        try:
            payload = json.loads(text)
            if not isinstance(payload, dict):
                raise CaptureError("trace JSON must be an object")
            return cls(
                schema=payload["schema"],
                skill_name=payload["skill_name"],
                skill_content_hash=payload["skill_content_hash"],
                task_sha256=payload["task_sha256"],
                cause=payload["cause"],
                input_tokens=payload["input_tokens"],
                output_tokens=payload["output_tokens"],
                cost_usd=payload["cost_usd"],
                events=tuple(
                    Event(
                        kind=EventKind(item["kind"]),
                        outcome=EventOutcome(item["outcome"]),
                        target=item["target"],
                        input_sha256=item["input_sha256"],
                        content_sha256=item["content_sha256"],
                        content_bytes=item["content_bytes"],
                        excerpt=item["excerpt"],
                        denials=tuple(item["denials"]),
                    )
                    for item in payload["events"]
                ),
            )
        except CaptureError:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise CaptureError(f"invalid trace JSON: {exc}") from None
