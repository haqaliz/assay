"""The provider seam: one reply per call, tools always supplied by the driver."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol, Sequence

from .records import ModelPrice, ToolCall, Usage
from .tools import ToolSpec


@dataclass(frozen=True, slots=True)
class Message:
    role: Literal["system", "user", "assistant", "tool"]
    content: str
    tool_call_id: str | None = None
    tool_calls: tuple[ToolCall, ...] = ()


@dataclass(frozen=True, slots=True)
class ModelReply:
    text: str | None
    tool_calls: tuple[ToolCall, ...]
    usage: Usage


class Model(Protocol):
    price: ModelPrice
    max_tokens: int

    def complete(self, messages: Sequence[Message], tools: Sequence[ToolSpec]) -> ModelReply: ...
