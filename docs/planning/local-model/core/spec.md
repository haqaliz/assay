# Spec — `local-model` / `core`

## Acceptance criteria

1. `OpenAICompatibleModel.complete` posts to `<base_url.rstrip("/")>/chat/completions` with headers
   `content-type: application/json`, `accept: application/json`, and `authorization: Bearer <key>`
   only when a key exists; the body contains `model`, `messages`, `tools`, `max_tokens`, `stream:false`
   and never the key.
2. Message mapping: `system`/`user` unchanged; `assistant` carries `content` (or null) and
   `tool_calls` (`id`, `type:"function"`, `function.name`, JSON-string `arguments`); each `tool`
   message becomes `{"role":"tool","tool_call_id":…,"content":…}`.
3. Tool mapping: `{"type":"function","function":{"name","description","parameters": <schema>}}`.
4. Response: `content` may be null; `tool_calls` arguments are JSON-decoded into a mapping (invalid
   JSON or non-object → `ModelFailed`); usage maps to `Usage`; `finish_reason` `length` or
   `content_filter` → `ModelFailed`.
5. Loopback (`localhost`, `127.0.0.0/8`, `::1`) may run keyless and ignores an ambient
   `ASSAY_API_KEY` (an explicit `api_key` is still sent). A non-loopback host must use https and
   without a key raises `AgentUnavailable` with `cause=MISSING_KEY` before any transport call. A key
   containing any non-printable character raises `AgentUnavailable` without echoing it. Environment
   proxies are disabled and redirects are refused for every model call.
6. HTTP/URL/timeout/`HTTPException`/transport `ValueError`/bad JSON/bad shape → `ModelFailed`; an
   HTTP error body is included, bounded to 500 bytes; the key never appears in a message.
7. CLI: `--provider` defaults to `anthropic`; `openai-compatible` requires `--base-url`; `--base-url`
   and `--api-key` with anthropic are usage errors; `--api-key` overrides `ASSAY_API_KEY`;
   model/prices/cap remain required; the banner includes the provider and base URL but never the
   key; a directory argument resolves to `SKILL.md`.
8. Tests: adapter request/response with an injected transport; CLI selection with a monkeypatched
   constructor; no sockets, no real Ollama call in the suite.

## Out of scope

Streaming, retries, provider-specific fields, config files, subscription auth, detection changes.
