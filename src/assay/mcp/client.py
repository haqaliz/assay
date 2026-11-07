"""Minimal MCP stdio client: newline-delimited JSON-RPC 2.0 over a line session."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Mapping, Protocol

PROTOCOL_VERSION = "2026-07-28"  # Pinned to the fixture; provisional for the spike.
MAX_LINE_BYTES = 1_048_576
CLIENT_NAME = "assay"
CLIENT_VERSION = "spike"


class LineSession(Protocol):
    def write_line(self, line: str) -> None: ...

    def read_line(self, deadline: float) -> str: ...

    def close(self) -> object: ...


class MCPError(RuntimeError):
    """The server or the transport failed a request."""


class MCPTimeout(MCPError):
    """The request deadline elapsed."""


class MCPProtocolError(MCPError):
    """The peer sent something that is not valid MCP/JSON-RPC."""


@dataclass(frozen=True, slots=True)
class MCPTool:
    name: str
    description: str
    input_schema: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class MCPResult:
    ok: bool
    text: str
    raw: Mapping[str, object] | None = None


class MCPClient:
    def __init__(self, session: LineSession, *, timeout: float = 10.0) -> None:
        self._session = session
        self._timeout = timeout
        self._next_id = 0

    def initialize(self) -> Mapping[str, object]:
        result = self._request(
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": CLIENT_NAME, "version": CLIENT_VERSION},
            },
        )
        version = result.get("protocolVersion")
        if not isinstance(version, str):
            raise MCPProtocolError("initialize: protocolVersion must be a string")
        self._notify("notifications/initialized")
        return result

    def list_tools(self) -> tuple[MCPTool, ...]:
        result = self._request("tools/list", {})
        tools = result.get("tools", [])
        if not isinstance(tools, list):
            raise MCPProtocolError("tools/list: tools must be a list")
        parsed: list[MCPTool] = []
        for item in tools:
            if not isinstance(item, dict):
                raise MCPProtocolError("tools/list: each tool must be an object")
            name = item.get("name")
            if not isinstance(name, str) or not name:
                raise MCPProtocolError("tools/list: tool name must be a non-empty string")
            description = item.get("description", "")
            if not isinstance(description, str):
                raise MCPProtocolError("tools/list: tool description must be a string")
            schema = item.get("inputSchema", {})
            if not isinstance(schema, dict):
                raise MCPProtocolError("tools/list: inputSchema must be an object")
            parsed.append(MCPTool(name, description, schema))
        return tuple(parsed)

    def call_tool(
        self,
        name: str,
        arguments: Mapping[str, object] | None = None,
        *,
        timeout: float | None = None,
    ) -> MCPResult:
        result = self._request(
            "tools/call",
            {"name": name, "arguments": dict(arguments or {})},
            timeout=timeout,
        )
        content = result.get("content", [])
        if not isinstance(content, list):
            raise MCPProtocolError("tools/call: content must be a list")
        parts: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                raise MCPProtocolError("tools/call: each content item must be an object")
            if item.get("type") == "text" and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return MCPResult(
            ok=not bool(result.get("isError", False)),
            text="".join(parts),
            raw=result,
        )

    def close(self) -> None:
        self._session.close()

    def __enter__(self) -> "MCPClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _request(
        self,
        method: str,
        params: Mapping[str, object],
        *,
        timeout: float | None = None,
    ) -> Mapping[str, object]:
        self._next_id += 1
        request_id = self._next_id
        self._send(
            {"jsonrpc": "2.0", "id": request_id, "method": method, "params": dict(params)}
        )
        deadline = time.monotonic() + (self._timeout if timeout is None else timeout)
        while True:
            message = self._read(deadline)
            if "id" not in message:
                if "method" in message:
                    continue
                raise MCPProtocolError("response has neither id nor method")
            if message["id"] != request_id:
                raise MCPProtocolError(
                    f"{method}: unexpected response id {message['id']!r}"
                )
            if "error" in message:
                error = message["error"]
                if not isinstance(error, dict):
                    raise MCPProtocolError(f"{method}: error must be an object")
                code = error.get("code")
                text = error.get("message")
                raise MCPError(f"{method}: {code}: {text}")
            result = message.get("result")
            if not isinstance(result, dict):
                raise MCPProtocolError(f"{method}: result must be an object")
            return result

    def _notify(self, method: str) -> None:
        self._send({"jsonrpc": "2.0", "method": method})

    def _send(self, message: Mapping[str, object]) -> None:
        line = json.dumps(message, separators=(",", ":"), ensure_ascii=False)
        if len(line.encode("utf-8")) > MAX_LINE_BYTES:
            raise MCPProtocolError("request line exceeds the maximum size")
        self._session.write_line(line)

    def _read(self, deadline: float) -> Mapping[str, object]:
        try:
            line = self._session.read_line(deadline)
        except TimeoutError as exc:
            raise MCPTimeout("timed out waiting for a response") from exc
        try:
            message = json.loads(line)
        except json.JSONDecodeError as exc:
            raise MCPProtocolError(f"response is not JSON: {exc.msg}") from exc
        if not isinstance(message, dict):
            raise MCPProtocolError("response must be a JSON object")
        return message
