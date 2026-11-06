import json
from collections import deque

import pytest

from assay.mcp.client import (
    MCPClient,
    MCPError,
    MCPProtocolError,
    MCPTimeout,
    PROTOCOL_VERSION,
)


class FakeSession:
    def __init__(self, *lines):
        self.lines = deque(lines)
        self.sent = []
        self.closed = False

    def write_line(self, line):
        self.sent.append(json.loads(line))

    def read_line(self, deadline):
        if not self.lines:
            raise TimeoutError("no line")
        item = self.lines.popleft()
        if isinstance(item, BaseException):
            raise item
        return item

    def close(self):
        self.closed = True


def reply(request_id, result):
    return json.dumps({"jsonrpc": "2.0", "id": request_id, "result": result})


def error(request_id, code, message):
    return json.dumps(
        {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}
    )


def initialized(request_id):
    return reply(
        request_id,
        {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "fixture", "version": "1"},
        },
    )


def test_initialize_sends_handshake_and_notification():
    session = FakeSession(initialized(1))
    client = MCPClient(session)

    result = client.initialize()

    assert result["protocolVersion"] == PROTOCOL_VERSION
    assert session.sent[0]["method"] == "initialize"
    assert session.sent[0]["params"]["protocolVersion"] == PROTOCOL_VERSION
    assert session.sent[0]["params"]["clientInfo"]["name"] == "assay"
    assert session.sent[1] == {"jsonrpc": "2.0", "method": "notifications/initialized"}


def test_initialize_rejects_a_non_string_protocol_version():
    session = FakeSession(reply(1, {"protocolVersion": 3}))
    client = MCPClient(session)

    with pytest.raises(MCPProtocolError, match="protocolVersion"):
        client.initialize()


def test_list_tools_maps_the_tool_shape():
    session = FakeSession(
        reply(
            1,
            {
                "tools": [
                    {
                        "name": "echo",
                        "description": "Echo text",
                        "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}}},
                    }
                ]
            },
        )
    )
    client = MCPClient(session)

    tools = client.list_tools()

    assert len(tools) == 1
    assert tools[0].name == "echo"
    assert tools[0].description == "Echo text"
    assert tools[0].input_schema["properties"]["text"]["type"] == "string"
    assert session.sent[0]["method"] == "tools/list"


def test_list_tools_rejects_a_non_list_payload():
    session = FakeSession(reply(1, {"tools": {"name": "echo"}}))
    client = MCPClient(session)

    with pytest.raises(MCPProtocolError, match="tools"):
        client.list_tools()


def test_call_tool_concatenates_text_content():
    session = FakeSession(
        reply(
            1,
            {
                "content": [
                    {"type": "text", "text": "a"},
                    {"type": "text", "text": "b"},
                ],
                "isError": False,
            },
        )
    )
    client = MCPClient(session)

    result = client.call_tool("echo", {"text": "hi"})

    assert result.ok
    assert result.text == "ab"
    assert session.sent[0]["method"] == "tools/call"
    assert session.sent[0]["params"] == {"name": "echo", "arguments": {"text": "hi"}}


def test_call_tool_preserves_is_error():
    session = FakeSession(
        reply(1, {"content": [{"type": "text", "text": "denied"}], "isError": True})
    )
    client = MCPClient(session)

    result = client.call_tool("read_outside", {})

    assert not result.ok
    assert result.text == "denied"


def test_json_rpc_error_raises():
    session = FakeSession(error(1, -32601, "Method not found"))
    client = MCPClient(session)

    with pytest.raises(MCPError, match="Method not found"):
        client.call_tool("missing", {})


def test_malformed_json_raises_a_protocol_error():
    session = FakeSession("not json")
    client = MCPClient(session)

    with pytest.raises(MCPProtocolError, match="JSON"):
        client.list_tools()


def test_non_object_json_raises_a_protocol_error():
    session = FakeSession("[1, 2]")
    client = MCPClient(session)

    with pytest.raises(MCPProtocolError, match="object"):
        client.list_tools()


def test_unmatched_response_id_raises():
    session = FakeSession(reply(99, {"tools": []}))
    client = MCPClient(session)

    with pytest.raises(MCPProtocolError, match="id"):
        client.list_tools()


def test_a_notification_before_the_response_is_skipped():
    session = FakeSession(
        json.dumps({"jsonrpc": "2.0", "method": "notifications/progress", "params": {}}),
        reply(1, {"tools": []}),
    )
    client = MCPClient(session)

    assert client.list_tools() == ()


def test_a_timeout_raises_mcp_timeout():
    session = FakeSession()
    client = MCPClient(session)

    with pytest.raises(MCPTimeout):
        client.list_tools()


def test_close_closes_the_session():
    session = FakeSession()
    client = MCPClient(session)

    client.close()

    assert session.closed
