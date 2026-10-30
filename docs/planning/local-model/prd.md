# PRD — `local-model` (OpenAI-compatible provider for keyless runs)

Status: approved 2026-10-31.
Pipeline position: provider #2 behind A3's `Model` seam (the deferred nice-to-have). Unblocks the
Phase 0 gate run without a paid key: the dev machine runs Ollama (`qwen3-coder:30b`) at
`http://127.0.0.1:11434/v1`.

## Problem statement

The Phase 0 gate needs one real keyed (or otherwise model-driven) run. The user has no Anthropic API
key, and the consumer-subscription route is forbidden by `CLAUDE.md` and R6. A local model server is
the only zero-key, zero-cost path that respects the project's rules.

For whom: the maintainer running the gate now, and every later user who wants to try Assay without
buying tokens.

## Goals and success metrics

| Goal | Metric |
|---|---|
| Run against Ollama with no key | A real `assay check` against `qwen3-coder:30b` completes and saves a trace |
| No key sent to a remote host by accident | A non-loopback base URL without a key refuses before any request |
| The key never leaks | Not in the request body, stdout/stderr, JSON or trace; control characters refused without echo |
| Same seam, no new dependency | `OpenAICompatibleModel` satisfies `Model`; stdlib HTTP with an injected transport |
| Offline tests | Request/response mapping and CLI selection tested with an injected transport; no sockets |
| Gate observation | The real Plumb `plumb-next` run against Ollama observed two undeclared shell commands: `FLAGGED`, exit 1, trace saved |

## Requirements

1. `OpenAICompatibleModel(model, price, base_url, api_key=None, max_tokens=1024, transport=None)`
   posts to `<base_url>/chat/completions`.
2. Auth: loopback base (`localhost`, any IP with `is_loopback`) may omit the key and ignores an
   ambient `ASSAY_API_KEY`; any other host must be **https** and requires `ASSAY_API_KEY` or
   `--api-key`, else `AgentUnavailable(MISSING_KEY)` before a request. The key goes only in
   `Authorization: Bearer …`, is redacted from error details, is never sent through an environment
   proxy, and is never forwarded across a redirect (redirects are refused).
3. Request mapping: system/user/assistant/tool messages, `tool_calls` with JSON-string arguments,
   tools as `{"type":"function","function":{...}}`, `stream:false`, `max_tokens`.
4. Response mapping: `choices[0].message.content` (nullable), `tool_calls` (arguments parsed to a
   mapping), `usage.prompt_tokens`/`completion_tokens`; `finish_reason` `length`/`content_filter` is
   `ModelFailed`.
5. Errors: HTTP (bounded body), URL, timeout, `http.client.HTTPException`, transport `ValueError`,
   malformed JSON or shape → `ModelFailed`; no key in any message.
6. CLI: `--provider {anthropic,openai-compatible}` (default anthropic), `--base-url` (required for
   the new provider, rejected for anthropic), `--api-key`/`ASSAY_API_KEY`. Model, prices and
   `--max-cost` stay required; prices may be `0` for a local model.
7. The pre-run stderr banner names the provider (and base URL) and the cap, never the key.
   `--base-url` and `--api-key` are rejected for the Anthropic provider; `<skill>` may be a file or
   its directory.
8. No new dependency; tests offline.

## Out of scope

Streaming, retries, other provider quirks, embeddings, a model picker, config files, subscription
automation (still forbidden), any detection change.

## Gate result (2026-10-31)

`assay check ~/dev/at/plumb/.claude/skills/plumb-next` against `qwen3-coder:30b` on Ollama, no key:
the agent ran `ls -la docs/planning/` and `git log --oneline -10`; the skill declares no tool scope.
Verdict `FLAGGED`, exit 1, trace saved and copied to the maintainer's Desktop. The pipeline is
proven end to end; this is not a Claude run and M0.3's full dogfood remains partial.

## Risks

| Risk | Mitigation |
|---|---|
| A weak local model produces poor tool calls, so the run triggers nothing | Honest `UNVERIFIED/NO_TRIGGER`; the gate proves the pipeline, not Claude-equivalent behavior |
| A typo in `--base-url` ships an unauthenticated request to a remote host | Loopback-only keyless rule; non-local URLs must be https |
| An environment proxy or a 30x forwards the key | Proxies disabled for model calls; redirects refused |
| A server echoes the key in an error body | Error detail is redacted against the key |
| Provider-specific response drift | Strict shape validation; every failure is `ModelFailed`, never a crash |
