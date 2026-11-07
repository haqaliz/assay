#!/usr/bin/env python3
"""Tiny stdio MCP server used by the sandbox-session tests. Standard library only."""

import json
import sys
import time
from pathlib import Path

TOOLS = [
    {
        "name": "echo",
        "description": "Echo the supplied text.",
        "inputSchema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    },
    {
        "name": "read_inside",
        "description": "Read a relative path under the run root.",
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    {
        "name": "read_outside",
        "description": "Attempt to read a host file; the jail should deny it.",
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
        },
    },
    {
        "name": "slow",
        "description": "Sleep, for the request-timeout test.",
        "inputSchema": {
            "type": "object",
            "properties": {"seconds": {"type": "number"}},
        },
    },
]


def send(message):
    sys.stdout.write(json.dumps(message, separators=(",", ":"), ensure_ascii=False) + "\n")
    sys.stdout.flush()


def text_result(text, *, is_error=False):
    return {"content": [{"type": "text", "text": text}], "isError": is_error}


def call_tool(name, arguments):
    if name == "echo":
        return text_result(str(arguments.get("text", "")))
    if name == "read_inside":
        try:
            return text_result(Path(arguments["path"]).read_text())
        except (KeyError, OSError) as exc:
            return text_result(f"read failed: {exc}", is_error=True)
    if name == "read_outside":
        path = Path(arguments.get("path", "/private/etc/hosts"))
        try:
            return text_result(path.read_text())
        except OSError as exc:
            sys.stderr.write(f"assay-denial: file-read {path} {exc}\n")
            sys.stderr.flush()
            return text_result(f"denied: {exc}", is_error=True)
    if name == "slow":
        time.sleep(float(arguments.get("seconds", 5)))
        return text_result("slept")
    raise LookupError(f"unknown tool: {name}")


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(message, dict) or "id" not in message:
            continue
        request_id = message["id"]
        method = message.get("method")
        params = message.get("params") or {}
        if method == "initialize":
            send(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "protocolVersion": params.get("protocolVersion", "2026-07-28"),
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "assay-mcp-fixture", "version": "1"},
                    },
                }
            )
        elif method == "tools/list":
            send({"jsonrpc": "2.0", "id": request_id, "result": {"tools": TOOLS}})
        elif method == "tools/call":
            try:
                result = call_tool(params.get("name"), params.get("arguments") or {})
            except LookupError as exc:
                send(
                    {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {"code": -32601, "message": str(exc)},
                    }
                )
            else:
                send({"jsonrpc": "2.0", "id": request_id, "result": result})
        else:
            send(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32601, "message": f"unknown method: {method}"},
                }
            )


if __name__ == "__main__":
    main()
