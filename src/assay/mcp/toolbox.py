"""Register MCP server tools with the driver and capture each call as evidence."""

from __future__ import annotations

import re
from typing import Sequence

from assay.agent.records import ToolCall, ToolResult
from assay.agent.tools import ToolSpec
from assay.capture import Event, EventOutcome
from assay.verdict import Finding, FindingClass, Severity
from assay.verdict.assess import instruction_labels

from .client import MCPClient, MCPError, MCPResult, MCPTool
from .events import event_for_call

_TOOL_NAME = re.compile(r"^[A-Za-z0-9_-]{1,59}$")


class MCPToolboxError(RuntimeError):
    """A server tool cannot be registered safely."""


class MCPToolbox:
    def __init__(self, client: MCPClient, tools: Sequence[MCPTool]) -> None:
        self._client = client
        self._mapping: dict[str, MCPTool] = {}
        self._specs: list[ToolSpec] = []
        self._events: list[Event] = []
        self._findings: list[Finding] = []
        self._seen: set[tuple[str, str]] = set()

        for tool in tools:
            if not _TOOL_NAME.fullmatch(tool.name):
                raise MCPToolboxError(
                    f"tool name {tool.name!r} is not provider-safe; "
                    "use 1-59 letters, digits, '_' or '-'"
                )
            spec_name = f"mcp__{tool.name}"
            if spec_name in self._mapping:
                raise MCPToolboxError(f"duplicate tool name {tool.name!r}")
            schema = dict(tool.input_schema) if tool.input_schema else {}
            if not schema:
                schema = {"type": "object", "properties": {}}
            schema.setdefault("type", "object")
            self._mapping[spec_name] = tool
            self._specs.append(ToolSpec(spec_name, tool.description, schema))
            self._scan(
                tool.description,
                target=f"tool:{tool.name}",
                source="tool description",
            )

    @property
    def tools(self) -> tuple[ToolSpec, ...]:
        return tuple(self._specs)

    @property
    def events(self) -> tuple[Event, ...]:
        return tuple(self._events)

    @property
    def findings(self) -> tuple[Finding, ...]:
        return tuple(self._findings)

    def execute(self, call: ToolCall) -> ToolResult:
        tool = self._mapping.get(call.name)
        if tool is None:
            return ToolResult(ok=False, output=f"unknown MCP tool {call.name!r}")
        arguments = dict(call.arguments)
        try:
            result = self._client.call_tool(tool.name, arguments)
        except MCPError as exc:
            result = MCPResult(ok=False, text=str(exc))
        self._events.append(event_for_call(tool.name, arguments, result))
        self._scan(
            result.text,
            target=f"result:{tool.name}",
            source="tool result",
        )
        output = result.text or ("ok" if result.ok else f"tool {tool.name!r} failed")
        return ToolResult(ok=result.ok, output=output, record=None)

    def _scan(self, text: str, *, target: str, source: str) -> None:
        for label in instruction_labels(text):
            key = (target, label)
            if key in self._seen:
                continue
            self._seen.add(key)
            self._findings.append(
                Finding(
                    class_=FindingClass.INSTRUCTIONS,
                    severity=Severity.REVIEW,
                    target=target,
                    reason=f"{source} matches {label!r}",
                    outcome=EventOutcome.OK,
                    review_required=True,
                )
            )
