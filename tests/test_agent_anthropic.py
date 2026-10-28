import json
import urllib.error

import pytest

from assay.agent import (
    AgentUnavailable,
    ModelFailed,
    ModelPrice,
    RunCause,
    ToolCall,
    Usage,
)
from assay.agent.anthropic import AnthropicModel
from assay.agent.base import Message
from assay.agent.tools import TOOLS

PRICE = ModelPrice(input_per_mtok=3.0, output_per_mtok=15.0)


def response(content, input_tokens=10, output_tokens=2):
    return json.dumps(
        {"content": content, "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens}}
    ).encode()


def capturing_transport(payload):
    seen = []

    def transport(request):
        seen.append(request)
        return payload

    return transport, seen


def body(request):
    return json.loads(request.data)


def headers(request):
    return {key.lower(): value for key, value in request.header_items()}


def test_from_env_without_key_refuses_before_any_call(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    called = []

    with pytest.raises(AgentUnavailable) as caught:
        AnthropicModel.from_env("claude-x", PRICE, transport=lambda req: called.append(req))
    assert caught.value.cause is RunCause.MISSING_KEY
    assert called == []


def test_from_env_uses_the_key_from_the_environment(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "env-secret")
    transport, seen = capturing_transport(response([{"type": "text", "text": "hi"}]))
    model = AnthropicModel.from_env("claude-x", PRICE, transport=transport)
    model.complete([Message("system", "BODY"), Message("user", "TASK")], TOOLS)
    assert headers(seen[0])["x-api-key"] == "env-secret"


def test_request_carries_the_documented_headers_and_body():
    transport, seen = capturing_transport(
        response([{"type": "text", "text": "hi"}], input_tokens=11, output_tokens=3)
    )
    model = AnthropicModel("claude-x", "secret", PRICE, transport=transport)
    reply = model.complete(
        [Message("system", "You are the skill."), Message("user", "Do the task.")], TOOLS
    )

    request = seen[0]
    assert request.full_url == "https://api.anthropic.com/v1/messages"
    assert request.get_method() == "POST"
    assert headers(request) == {
        "x-api-key": "secret",
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    sent = body(request)
    assert sent["model"] == "claude-x"
    assert sent["max_tokens"] == 1024
    assert sent["system"] == "You are the skill."
    assert sent["messages"] == [{"role": "user", "content": "Do the task."}]
    assert [tool["name"] for tool in sent["tools"]] == [
        "read_file",
        "write_file",
        "run_shell",
        "http_get",
    ]
    assert sent["tools"][0]["input_schema"] == TOOLS[0].input_schema
    assert b"secret" not in request.data

    assert reply.text == "hi"
    assert reply.tool_calls == ()
    assert reply.usage == Usage(input_tokens=11, output_tokens=3)


def test_missing_system_message_is_a_value_error_before_transport():
    called = []
    model = AnthropicModel("claude-x", "secret", PRICE, transport=lambda req: called.append(req))
    with pytest.raises(ValueError, match="system"):
        model.complete([Message("user", "TASK")], TOOLS)
    assert called == []


def test_assistant_text_and_tool_calls_and_grouped_tool_results_are_mapped():
    transport, seen = capturing_transport(response([{"type": "text", "text": "done"}]))
    model = AnthropicModel("claude-x", "secret", PRICE, transport=transport)
    calls = (
        ToolCall(id="t1", name="read_file", arguments={"path": "a.txt"}),
        ToolCall(id="t2", name="run_shell", arguments={"command": "true"}),
    )
    model.complete(
        [
            Message("system", "BODY"),
            Message("user", "TASK"),
            Message("assistant", "Looking.", tool_calls=calls),
            Message("tool", "file data", tool_call_id="t1"),
            Message("tool", "exit 0", tool_call_id="t2"),
        ],
        TOOLS,
    )
    messages = body(seen[0])["messages"]
    assert messages[0] == {"role": "user", "content": "TASK"}
    assert messages[1] == {
        "role": "assistant",
        "content": [
            {"type": "text", "text": "Looking."},
            {"type": "tool_use", "id": "t1", "name": "read_file", "input": {"path": "a.txt"}},
            {"type": "tool_use", "id": "t2", "name": "run_shell", "input": {"command": "true"}},
        ],
    }
    assert messages[2] == {
        "role": "user",
        "content": [
            {"type": "tool_result", "tool_use_id": "t1", "content": "file data"},
            {"type": "tool_result", "tool_use_id": "t2", "content": "exit 0"},
        ],
    }
    assert len(messages) == 3


def test_tool_use_blocks_are_parsed_with_out_text_as_none():
    transport, _ = capturing_transport(
        response(
            [
                {"type": "tool_use", "id": "t9", "name": "read_file", "input": {"path": "b"}},
            ]
        )
    )
    reply = AnthropicModel("claude-x", "secret", PRICE, transport=transport).complete(
        [Message("system", "BODY"), Message("user", "TASK")], TOOLS
    )
    assert reply.text is None
    assert reply.tool_calls == (ToolCall(id="t9", name="read_file", arguments={"path": "b"}),)


def test_explicit_endpoint_and_max_tokens_are_used():
    transport, seen = capturing_transport(response([{"type": "text", "text": "ok"}]))
    model = AnthropicModel(
        "claude-x",
        "secret",
        PRICE,
        max_tokens=256,
        transport=transport,
        endpoint="https://proxy.example/v1/messages",
    )
    model.complete([Message("system", "BODY"), Message("user", "TASK")], TOOLS)
    assert seen[0].full_url == "https://proxy.example/v1/messages"
    assert body(seen[0])["max_tokens"] == 256


@pytest.mark.parametrize(
    "failure",
    [
        urllib.error.HTTPError("https://api.anthropic.com", 500, "boom", None, None),
        urllib.error.URLError("no route"),
        TimeoutError("timed out"),
    ],
)
def test_transport_failures_become_model_failed(failure):
    def transport(request):
        raise failure

    model = AnthropicModel("claude-x", "secret", PRICE, transport=transport)
    with pytest.raises(ModelFailed):
        model.complete([Message("system", "BODY"), Message("user", "TASK")], TOOLS)


@pytest.mark.parametrize(
    "payload",
    [
        b"not json",
        json.dumps({"usage": {"input_tokens": 1, "output_tokens": 1}}).encode(),
        json.dumps({"content": "nope", "usage": {}}).encode(),
        json.dumps({"content": [{"type": "text"}], "usage": {}}).encode(),
        json.dumps(
            {
                "content": [{"type": "tool_use", "id": "t", "name": "read_file", "input": []}],
                "usage": {"input_tokens": 1, "output_tokens": 1},
            }
        ).encode(),
        b"[]",
    ],
)
def test_malformed_responses_become_model_failed(payload):
    model = AnthropicModel("claude-x", "secret", PRICE, transport=lambda req: payload)
    with pytest.raises(ModelFailed):
        model.complete([Message("system", "BODY"), Message("user", "TASK")], TOOLS)
