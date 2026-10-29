"""Types produced by the agent driver. No verdicts live here; A5 owns those."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum
from typing import Mapping

from assay.sandbox import RunRecord


class RunCause(StrEnum):
    MISSING_KEY = "missing-key"
    MODEL_FAILED = "model-failed"
    COST_CAPPED = "cost-capped"
    STEP_LIMIT = "step-limit"
    ACTION_LIMIT = "action-limit"
    WALL_LIMIT = "wall-limit"
    SANDBOX_UNAVAILABLE = "sandbox-unavailable"


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


@dataclass(frozen=True, slots=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0

    def __post_init__(self) -> None:
        _non_negative_int(self.input_tokens, "input_tokens")
        _non_negative_int(self.output_tokens, "output_tokens")

    def __add__(self, other: Usage) -> Usage:
        return Usage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
        )


@dataclass(frozen=True, slots=True)
class ModelPrice:
    """USD per million tokens; the caller supplies prices, nothing is hardcoded."""

    input_per_mtok: float
    output_per_mtok: float

    def __post_init__(self) -> None:
        _non_negative_float(self.input_per_mtok, "input_per_mtok")
        _non_negative_float(self.output_per_mtok, "output_per_mtok")

    def cost(self, usage: Usage) -> float:
        return (
            usage.input_tokens / 1_000_000 * self.input_per_mtok
            + usage.output_tokens / 1_000_000 * self.output_per_mtok
        )


@dataclass(frozen=True, slots=True)
class Budget:
    max_usd: float
    max_steps: int = 20
    max_actions: int = 40
    max_wall_seconds: float = 300.0

    def __post_init__(self) -> None:
        if (
            isinstance(self.max_usd, bool)
            or not isinstance(self.max_usd, (int, float))
            or not math.isfinite(self.max_usd)
            or self.max_usd <= 0
        ):
            raise ValueError(f"max_usd must be a finite positive number, got {self.max_usd!r}")
        if (
            isinstance(self.max_steps, bool)
            or not isinstance(self.max_steps, int)
            or self.max_steps < 1
        ):
            raise ValueError(f"max_steps must be an int >= 1, got {self.max_steps!r}")
        if (
            isinstance(self.max_actions, bool)
            or not isinstance(self.max_actions, int)
            or self.max_actions < 1
        ):
            raise ValueError(f"max_actions must be an int >= 1, got {self.max_actions!r}")
        if (
            isinstance(self.max_wall_seconds, bool)
            or not isinstance(self.max_wall_seconds, (int, float))
            or not math.isfinite(self.max_wall_seconds)
            or self.max_wall_seconds <= 0
        ):
            raise ValueError(
                f"max_wall_seconds must be a finite positive number, got {self.max_wall_seconds!r}"
            )


@dataclass(frozen=True, slots=True)
class ToolCall:
    id: str
    name: str
    arguments: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class ToolResult:
    ok: bool
    output: str
    record: RunRecord | None = None


@dataclass(frozen=True, slots=True)
class ToolAction:
    call: ToolCall
    result: ToolResult


@dataclass(frozen=True, slots=True)
class RunOutcome:
    cause: RunCause | None
    final_text: str | None
    steps: int
    actions: tuple[ToolAction, ...]
    usage: Usage
    cost_usd: float

    @property
    def finished(self) -> bool:
        return self.cause is None and self.final_text is not None


class AgentError(RuntimeError):
    """Base class; a run that cannot proceed is named, never silently skipped."""


class AgentUnavailable(AgentError):
    def __init__(self, detail: str, cause: RunCause | None = None) -> None:
        self.cause = cause
        super().__init__(detail)


class ModelFailed(AgentError):
    """The provider could not produce a reply; drive() maps this to MODEL_FAILED."""
