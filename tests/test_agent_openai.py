import http.client
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
from assay.agent.base import Message
from assay.agent.openai_compat import OpenAICompatibleModel
from assay.agent.tools import TOOLS

PRICE = ModelPrice(input_per_mtok=1.0, output_per_mtok=2.0)
LOCAL = "http://127.0.0.1:11434/v1"
REMOTE = "https://api.example.com/v1"


def reply(content=None, calls=None, input_tokens=10, output_tokens=2, finish="stop"):
    message = {"role": "assistant", "content": content}
    if calls is not None:
        message["tool_calls"] = calls
    return json.dumps(
        {
            "choices": [{"message": message, "finish_reason": finish}],
            "usage": {"prompt_tokens": input_tokens, "completion_tokens": output_tokens},
        }
    ).encode()


def tool_call(call_id="t1", name="read_file", arguments='{"path": "a.txt"}'):
    return {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": arguments},
    }


def capturing(payload):
    seen = []

    def transport(request):
        seen.append(request)
        return payload

    return transport, seen


def body(request):
    return json.loads(request.data)


def headers(request):
    return {key.lower(): value for key, value in request.header_items()}


def complete(model, messages=None, tools=TOOLS):
    return model.complete(
        messages or [Message("system", "BODY"), Message("user", "TASK")], tools
    )


def test_loopback_needs_no_key_and_posts_the_openai_shape():
    transport, seen = capturing(reply("hi"))
    model = OpenAICompatibleModel("qwen3-coder:30b", PRICE, LOCAL, transport=transport)

    result = complete(model)

    request = seen[0]
    assert request.full_url == f"{LOCAL}/chat/completions"
    assert "authorization" not in headers(request)
    payload = body(request)
    assert payload["model"] == "qwen3-coder:30b"
    assert payload["stream"] is False
    assert payload["max_tokens"] == 1024
    assert payload["messages"][0] == {"role": "system", "content": "BODY"}
    assert payload["tools"][0]["type"] == "function"
    assert payload["tools"][0]["function"]["name"] == "read_file"
    assert result.text == "hi"
    assert result.usage == Usage(10, 2)


def test_a_remote_host_without_a_key_refuses_before_any_request():
    called = []
    with pytest.raises(AgentUnavailable) as caught:
        OpenAICompatibleModel("m", PRICE, REMOTE, transport=lambda req: called.append(req))
    assert caught.value.cause is RunCause.MISSING_KEY
    assert called == []


def test_a_remote_host_sends_the_key_in_the_header_only():
    transport, seen = capturing(reply("hi"))
    model = OpenAICompatibleModel("m", PRICE, REMOTE, api_key="sk-secret", transport=transport)

    complete(model)

    assert headers(seen[0])["authorization"] == "Bearer sk-secret"
    assert "sk-secret" not in seen[0].data.decode()
    assert "sk-secret" not in seen[0].full_url


def test_a_control_character_key_is_refused_without_echo():
    with pytest.raises(AgentUnavailable) as caught:
        OpenAICompatibleModel("m", PRICE, REMOTE, api_key="sk-SECRET\n")
    assert "SECRET" not in str(caught.value)


def test_assistant_tool_calls_and_tool_results_are_mapped():
    transport, seen = capturing(reply("done"))
    model = OpenAICompatibleModel("m", PRICE, LOCAL, transport=transport)
    messages = [
        Message("system", "BODY"),
        Message("user", "TASK"),
        Message(
            "assistant",
            "working",
            tool_calls=(ToolCall(id="t1", name="read_file", arguments={"path": "a.txt"}),),
        ),
        Message("tool", "contents", tool_call_id="t1"),
    ]

    complete(model, messages)

    sent = body(seen[0])["messages"]
    assert sent[2]["role"] == "assistant"
    assert sent[2]["tool_calls"][0]["id"] == "t1"
    assert sent[2]["tool_calls"][0]["function"]["name"] == "read_file"
    assert json.loads(sent[2]["tool_calls"][0]["function"]["arguments"]) == {"path": "a.txt"}
    assert sent[3] == {"role": "tool", "tool_call_id": "t1", "content": "contents"}


def test_tool_calls_are_parsed_and_null_content_is_allowed():
    transport, _ = capturing(reply(None, [tool_call()]))
    model = OpenAICompatibleModel("m", PRICE, LOCAL, transport=transport)

    result = complete(model)

    assert result.text is None
    assert result.tool_calls[0].name == "read_file"
    assert result.tool_calls[0].arguments == {"path": "a.txt"}


def test_invalid_tool_arguments_are_model_failed():
    transport, _ = capturing(reply(None, [tool_call(arguments="not json")]))
    model = OpenAICompatibleModel("m", PRICE, LOCAL, transport=transport)
    with pytest.raises(ModelFailed, match="arguments"):
        complete(model)


def test_a_truncated_reply_is_model_failed():
    transport, _ = capturing(reply("partial", finish="length"))
    model = OpenAICompatibleModel("m", PRICE, LOCAL, transport=transport)
    with pytest.raises(ModelFailed, match="truncated"):
        complete(model)


@pytest.mark.parametrize(
    "failure",
    [
        urllib.error.HTTPError("http://x", 500, "boom", None, None),
        urllib.error.URLError("no route"),
        TimeoutError("timed out"),
        http.client.IncompleteRead(b"part"),
        ValueError("Invalid header value b'sk-SECRET'"),
    ],
)
def test_transport_failures_are_model_failed_without_echoing_a_key(failure):
    def transport(request):
        raise failure

    model = OpenAICompatibleModel("m", PRICE, REMOTE, api_key="sk-SECRET", transport=transport)
    with pytest.raises(ModelFailed) as caught:
        complete(model)
    assert "sk-SECRET" not in str(caught.value)


@pytest.mark.parametrize(
    "payload",
    [
        b"not json",
        b"[]",
        json.dumps({"choices": []}).encode(),
        json.dumps({"choices": [{"message": []}]}).encode(),
        json.dumps({"choices": [{"message": {"content": 1}}], "usage": {}}).encode(),
    ],
)
def test_malformed_responses_are_model_failed(payload):
    model = OpenAICompatibleModel("m", PRICE, LOCAL, transport=lambda req: payload)
    with pytest.raises(ModelFailed):
        complete(model)


@pytest.fixture(autouse=True)
def _no_ambient_key(monkeypatch):
    monkeypatch.delenv("ASSAY_API_KEY", raising=False)


def test_loopback_ignores_an_ambient_key(monkeypatch):
    monkeypatch.setenv("ASSAY_API_KEY", "sk-ambient")
    transport, seen = capturing(reply("hi"))
    model = OpenAICompatibleModel("m", PRICE, LOCAL, transport=transport)
    complete(model)
    assert "authorization" not in headers(seen[0])


def test_a_non_local_http_url_is_refused():
    with pytest.raises(ValueError, match="https"):
        OpenAICompatibleModel("m", PRICE, "http://api.example.com/v1", api_key="k")


def test_credentials_or_a_query_in_the_base_url_are_refused():
    for url in (
        "http://user:pass@127.0.0.1:11434/v1",
        "http://127.0.0.1:11434/v1?token=x",
        "http://127.0.0.1:11434/v1#frag",
        "http://127.0.0.1:abc/v1",
    ):
        with pytest.raises(ValueError):
            OpenAICompatibleModel("m", PRICE, url)


def test_usage_is_required_and_must_be_integers():
    for usage in (None, {}, {"prompt_tokens": 1}, {"prompt_tokens": 1.5, "completion_tokens": 2},
                  {"prompt_tokens": True, "completion_tokens": 2}):
        payload = json.dumps(
            {"choices": [{"message": {"content": "hi"}, "finish_reason": "stop"}],
             "usage": usage}
        ).encode()
        model = OpenAICompatibleModel("m", PRICE, LOCAL, transport=lambda req: payload)
        with pytest.raises(ModelFailed):
            complete(model)


@pytest.mark.parametrize("finish", ["max_tokens", "content_filter"])
def test_other_truncation_reasons_are_refused(finish):
    model = OpenAICompatibleModel(
        "m", PRICE, LOCAL, transport=lambda req: reply("part", finish=finish)
    )
    with pytest.raises(ModelFailed, match="truncated"):
        complete(model)


def test_an_empty_reply_is_model_failed():
    payload = json.dumps(
        {"choices": [{"message": {"content": None}, "finish_reason": "stop"}],
         "usage": {"prompt_tokens": 1, "completion_tokens": 1}}
    ).encode()
    model = OpenAICompatibleModel("m", PRICE, LOCAL, transport=lambda req: payload)
    with pytest.raises(ModelFailed, match="empty"):
        complete(model)


def test_object_arguments_and_text_content_blocks_are_accepted():
    payload = json.dumps(
        {
            "choices": [
                {
                    "message": {
                        "content": [{"type": "text", "text": "hi"}],
                        "tool_calls": [
                            {"id": "t1", "type": "function",
                             "function": {"name": "read_file", "arguments": {"path": "a"}}}
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        }
    ).encode()
    model = OpenAICompatibleModel("m", PRICE, LOCAL, transport=lambda req: payload)
    result = complete(model)
    assert result.text == "hi"
    assert result.tool_calls[0].arguments == {"path": "a"}


def test_an_error_body_cannot_echo_the_key():
    import io

    body = io.BytesIO(b'{"error":"bad key sk-SECRET"}')
    error = urllib.error.HTTPError("http://x", 401, "unauthorized", {}, body)
    model = OpenAICompatibleModel("m", PRICE, REMOTE, api_key="sk-SECRET",
                                  transport=lambda req: (_ for _ in ()).throw(error))
    with pytest.raises(ModelFailed) as caught:
        complete(model)
    assert "sk-SECRET" not in str(caught.value)


def test_a_c1_control_character_key_is_refused():
    with pytest.raises(AgentUnavailable):
        OpenAICompatibleModel("m", PRICE, REMOTE, api_key="sk-\x85")


def test_redirects_are_not_followed():
    import urllib.request

    from assay.agent.transport import _NoRedirect

    handler = _NoRedirect()
    assert handler.redirect_request(
        urllib.request.Request("https://a.example/x"), None, 302, "Found", {},
        "https://b.example/y",
    ) is None
