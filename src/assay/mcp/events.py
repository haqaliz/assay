"""Map MCP tool calls to capture evidence without touching the verdict contract."""

from __future__ import annotations

import hashlib
import json
from typing import Mapping, Sequence

from assay.capture import Event, EventKind, EventOutcome

from .client import MCPResult

EXCERPT_BYTES = 4096


def event_for_call(
    tool: str,
    arguments: Mapping[str, object],
    result: MCPResult,
    *,
    denials: Sequence[str] = (),
) -> Event:
    content = result.text.encode("utf-8")
    input_bytes = json.dumps(
        arguments, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    if denials:
        outcome = EventOutcome.DENIED
    elif result.ok:
        outcome = EventOutcome.OK
    else:
        outcome = EventOutcome.FAILED
    return Event(
        kind=EventKind.TOOL,
        outcome=outcome,
        target=tool,
        content_sha256=hashlib.sha256(content).hexdigest(),
        content_bytes=len(content),
        excerpt=content[:EXCERPT_BYTES].decode("utf-8", "replace"),
        input_sha256=hashlib.sha256(input_bytes).hexdigest(),
        request="tools/call",
        denials=tuple(denials),
        truncated=len(content) > EXCERPT_BYTES,
    )
