"""Anthropic Messages adapter over stdlib HTTP; tests inject the transport."""

from __future__ import annotations

import http.client
import json
import os
import urllib.error
import urllib.request
from typing import Callable, Mapping, Sequence

from .base import Message, ModelReply
from .records import AgentUnavailable, ModelFailed, ModelPrice, RunCause, ToolCall, Usage
from .tools import ToolSpec

DEFAULT_ENDPOINT = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
TIMEOUT_SECONDS = 60

Transport = Callable[[urllib.request.Request], bytes]


def _urlopen(request: urllib.request.Request) -> bytes:
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        return response.read()


class AnthropicModel:
    def __init__(
        self,
        model: str,
        api_key: str,
        price: ModelPrice,
        max_tokens: int = 1024,
        transport: Transport | None = None,
        endpoint: str = DEFAULT_ENDPOINT,
    ) -> None:
        if not isinstance(api_key, str) or not api_key.strip():
            raise AgentUnavailable("ANTHROPIC_API_KEY is not set", cause=RunCause.MISSING_KEY)
        if any(ord(char) < 32 or ord(char) == 127 for char in api_key):
            # Never echo the value: the exception is printed by the CLI.
            raise AgentUnavailable(
                "ANTHROPIC_API_KEY contains control characters", cause=RunCause.MISSING_KEY
            )
        if not isinstance(model, str) or not model:
            raise ValueError("model must be a non-empty string")
        if isinstance(max_tokens, bool) or not isinstance(max_tokens, int) or max_tokens < 1:
            raise ValueError(f"max_tokens must be an int >= 1, got {max_tokens!r}")
        self.model = model
        self.price = price
        self.max_tokens = max_tokens
        self.endpoint = endpoint
        self._api_key = api_key
        self._transport = transport or _urlopen

    @classmethod
    def from_env(cls, model: str, price: ModelPrice, **kwargs: object) -> AnthropicModel:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key or not api_key.strip():
            raise AgentUnavailable("ANTHROPIC_API_KEY is not set", cause=RunCause.MISSING_KEY)
        return cls(model, api_key, price, **kwargs)  # type: ignore[arg-type]

    def complete(self, messages: Sequence[Message], tools: Sequence[ToolSpec]) -> ModelReply:
        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(self._body(messages, tools)).encode(),
            headers={
                "x-api-key": self._api_key,
                "anthropic-version": ANTHROPIC_VERSION,
                "content-type": "application/json",
            },
            method="POST",
        )
        try:
            raw = self._transport(request)
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read(500).decode("utf-8", "replace")
            except Exception:
                pass
            raise ModelFailed(f"http {exc.code}: {detail or exc.reason}") from exc
        except (urllib.error.URLError, OSError, TimeoutError, http.client.HTTPException) as exc:
            raise ModelFailed(f"transport failed: {exc}") from exc
        except ValueError:
            # http.client includes the offending header value in its message; never echo it.
            raise ModelFailed("transport failed: invalid request") from None
        try:
            return self._parse(raw)
        except (json.JSONDecodeError, UnicodeDecodeError, KeyError, TypeError, ValueError) as exc:
            raise ModelFailed(f"malformed response: {exc}") from exc

    def _body(self, messages: Sequence[Message], tools: Sequence[ToolSpec]) -> dict:
        system: str | None = None
        converted: list[dict] = []
        tool_results: list[dict] = []

        def flush_results() -> None:
            if tool_results:
                converted.append({"role": "user", "content": list(tool_results)})
                tool_results.clear()

        for message in messages:
            if message.role == "system":
                system = message.content
            elif message.role == "tool":
                if message.tool_call_id is None:
                    raise ValueError("tool messages need a tool_call_id")
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": message.tool_call_id,
                        "content": message.content,
                    }
                )
            elif message.role == "assistant":
                flush_results()
                blocks: list[dict] = []
                if message.content:
                    blocks.append({"type": "text", "text": message.content})
                blocks.extend(
                    {
                        "type": "tool_use",
                        "id": call.id,
                        "name": call.name,
                        "input": dict(call.arguments),
                    }
                    for call in message.tool_calls
                )
                converted.append({"role": "assistant", "content": blocks or ""})
            elif message.role == "user":
                flush_results()
                converted.append({"role": "user", "content": message.content})
            else:
                raise ValueError(f"unsupported message role: {message.role!r}")
        flush_results()

        if system is None:
            raise ValueError("messages must include a system message")
        return {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": system,
            "messages": converted,
            "tools": [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.input_schema,
                }
                for tool in tools
            ],
        }

    @staticmethod
    def _parse(raw: object) -> ModelReply:
        payload = json.loads(raw)  # type: ignore[arg-type]
        if not isinstance(payload, dict):
            raise ModelFailed("response is not a JSON object")
        if payload.get("stop_reason") in ("max_tokens", "refusal", "pause_turn"):
            raise ModelFailed(f"response truncated or refused: {payload.get('stop_reason')}")
        content = payload["content"]
        if not isinstance(content, list):
            raise ModelFailed("response content must be a list")

        texts: list[str] = []
        calls: list[ToolCall] = []
        for block in content:
            if not isinstance(block, dict):
                raise ModelFailed(f"content block must be an object, got {block!r}")
            if block.get("type") == "text":
                text = block["text"]
                if not isinstance(text, str):
                    raise ModelFailed("text block value must be a string")
                texts.append(text)
            elif block.get("type") == "tool_use":
                args = block["input"]
                if not isinstance(block.get("id"), str) or not isinstance(block.get("name"), str):
                    raise ModelFailed("tool_use block needs a string id and name")
                if not isinstance(args, Mapping):
                    raise ModelFailed("tool_use input must be an object")
                calls.append(ToolCall(id=block["id"], name=block["name"], arguments=args))

        usage = payload["usage"]
        if not isinstance(usage, dict):
            raise ModelFailed("response usage must be an object")
        return ModelReply(
            text="".join(texts) if texts else None,
            tool_calls=tuple(calls),
            usage=Usage(
                input_tokens=usage["input_tokens"], output_tokens=usage["output_tokens"]
            ),
        )
