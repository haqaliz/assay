"""OpenAI-compatible chat adapter: one seam for Ollama, OpenAI, OpenRouter and friends."""

from __future__ import annotations

import http.client
import ipaddress
import json
import os
import urllib.error
import urllib.request
from typing import Mapping, Sequence
from urllib.parse import urlsplit

from .base import Message, ModelReply
from .records import AgentUnavailable, ModelFailed, ModelPrice, RunCause, ToolCall, Usage
from .tools import ToolSpec
from .transport import redact, urlopen_bounded

TIMEOUT_SECONDS = 60
_TRUNCATED = ("length", "max_tokens", "content_filter")


def _is_loopback(host: str) -> bool:
    if host.rstrip(".") == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _has_control(value: str) -> bool:
    return any(not char.isprintable() for char in value)


class OpenAICompatibleModel:
    def __init__(
        self,
        model: str,
        price: ModelPrice,
        base_url: str,
        api_key: str | None = None,
        max_tokens: int = 1024,
        transport=None,
    ) -> None:
        if not isinstance(model, str) or not model.strip():
            raise ValueError("model must be a non-empty string")
        if isinstance(max_tokens, bool) or not isinstance(max_tokens, int) or max_tokens < 1:
            raise ValueError(f"max_tokens must be an int >= 1, got {max_tokens!r}")
        parts = urlsplit(base_url)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            raise ValueError("base_url must be an http or https URL with a host")
        if parts.username or parts.password or parts.query or parts.fragment:
            raise ValueError("base_url must not carry credentials, a query or a fragment")
        try:
            parts.port
        except ValueError:
            raise ValueError("base_url port must be numeric") from None
        local = _is_loopback(parts.hostname)
        if not local and parts.scheme != "https":
            raise ValueError("a non-local base_url must use https")
        # An ambient key is for remote providers only; a local server gets a key only when the
        # caller passes one explicitly.
        key = api_key if api_key is not None else None if local else os.environ.get("ASSAY_API_KEY")
        if not local and (not key or not key.strip()):
            raise AgentUnavailable(
                "ASSAY_API_KEY is required for a non-local base URL",
                cause=RunCause.MISSING_KEY,
            )
        if key is not None:
            if _has_control(key):
                raise AgentUnavailable(
                    "ASSAY_API_KEY contains control characters", cause=RunCause.MISSING_KEY
                )
            if not key.strip():
                key = None
        self.model = model
        self.price = price
        self.max_tokens = max_tokens
        self.endpoint = base_url.rstrip("/") + "/chat/completions"
        self._api_key = key
        self._transport = transport or urlopen_bounded

    def complete(self, messages: Sequence[Message], tools: Sequence[ToolSpec]) -> ModelReply:
        try:
            body = json.dumps(self._body(messages, tools)).encode()
        except (TypeError, ValueError) as exc:
            raise ModelFailed(f"invalid request: {exc}") from None
        headers = {"content-type": "application/json", "accept": "application/json"}
        if self._api_key is not None:
            headers["authorization"] = f"Bearer {self._api_key}"
        request = urllib.request.Request(self.endpoint, data=body, headers=headers, method="POST")
        try:
            raw = self._transport(request)
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read(500).decode("utf-8", "replace")
            except Exception:
                pass
            message = redact(f"http {exc.code}: {detail or exc.reason}", self._api_key)
            raise ModelFailed(message) from exc
        except (urllib.error.URLError, OSError, TimeoutError, http.client.HTTPException) as exc:
            raise ModelFailed(f"transport failed: {exc}") from exc
        except ValueError:
            # http.client includes the offending header value in its message; never echo it.
            raise ModelFailed("transport failed: invalid request") from None
        try:
            return self._parse(raw)
        except ModelFailed:
            raise
        except (
            json.JSONDecodeError,
            UnicodeDecodeError,
            KeyError,
            TypeError,
            ValueError,
            OverflowError,
            RecursionError,
        ) as exc:
            raise ModelFailed(f"malformed response: {exc}") from exc

    def _body(self, messages: Sequence[Message], tools: Sequence[ToolSpec]) -> dict:
        converted: list[dict] = []
        for message in messages:
            if message.role == "assistant":
                item: dict = {"role": "assistant", "content": message.content or None}
                if message.tool_calls:
                    item["tool_calls"] = [
                        {
                            "id": call.id,
                            "type": "function",
                            "function": {
                                "name": call.name,
                                "arguments": json.dumps(dict(call.arguments)),
                            },
                        }
                        for call in message.tool_calls
                    ]
                converted.append(item)
            elif message.role == "tool":
                if message.tool_call_id is None:
                    raise ValueError("tool messages need a tool_call_id")
                converted.append(
                    {
                        "role": "tool",
                        "tool_call_id": message.tool_call_id,
                        "content": message.content,
                    }
                )
            elif message.role in ("system", "user"):
                converted.append({"role": message.role, "content": message.content})
            else:
                raise ValueError(f"unsupported message role: {message.role!r}")
        return {
            "model": self.model,
            "messages": converted,
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": dict(tool.input_schema),
                    },
                }
                for tool in tools
            ],
            "max_tokens": self.max_tokens,
            "stream": False,
        }

    @staticmethod
    def _parse(raw: object) -> ModelReply:
        payload = json.loads(raw)  # type: ignore[arg-type]
        if not isinstance(payload, dict):
            raise ModelFailed("response is not a JSON object")
        choices = payload["choices"]
        if not isinstance(choices, list) or not choices:
            raise ModelFailed("response choices must be a non-empty list")
        choice = choices[0]
        if not isinstance(choice, dict) or not isinstance(choice.get("message"), dict):
            raise ModelFailed("response choice must carry a message object")
        if choice.get("finish_reason") in _TRUNCATED:
            raise ModelFailed(f"response truncated or filtered: {choice.get('finish_reason')}")
        content = _content(choice["message"].get("content"))
        calls = choice["message"].get("tool_calls") or []
        if not isinstance(calls, list):
            raise ModelFailed("response tool_calls must be a list")
        tool_calls = []
        for call in calls:
            if not isinstance(call, dict) or not isinstance(call.get("function"), dict):
                raise ModelFailed("tool call must carry a function object")
            function = call["function"]
            if not isinstance(call.get("id"), str) or not isinstance(function.get("name"), str):
                raise ModelFailed("tool call needs a string id and name")
            arguments = function.get("arguments", "{}")
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except json.JSONDecodeError as exc:
                    raise ModelFailed(f"tool call arguments are not JSON: {exc}") from None
            if not isinstance(arguments, Mapping):
                raise ModelFailed("tool call arguments must be a JSON object")
            tool_calls.append(ToolCall(id=call["id"], name=function["name"], arguments=arguments))
        if not content and not tool_calls:
            raise ModelFailed("empty reply: no content and no tool calls")
        usage = payload.get("usage")
        if not isinstance(usage, dict):
            raise ModelFailed("response usage must be an object")
        return ModelReply(
            text=content,
            tool_calls=tuple(tool_calls),
            usage=Usage(
                input_tokens=_tokens(usage, "prompt_tokens"),
                output_tokens=_tokens(usage, "completion_tokens"),
            ),
        )


def _content(value: object) -> str | None:
    if value is None or isinstance(value, str):
        return value
    if isinstance(value, list):
        texts = []
        for block in value:
            if not isinstance(block, dict) or block.get("type") != "text":
                raise ModelFailed("only text content blocks are supported")
            text = block.get("text")
            if not isinstance(text, str):
                raise ModelFailed("text content blocks need a string text")
            texts.append(text)
        return "".join(texts) or None
    raise ModelFailed("response content must be a string, text blocks or null")


def _tokens(usage: dict, key: str) -> int:
    value = usage.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ModelFailed(f"usage.{key} must be a non-negative integer")
    return value
