# feat local-model — OpenAI-compatible model adapter for keyless local runs

## Brief

> Add a second `Model` adapter for the OpenAI-compatible chat-completions protocol, and let the CLI
> select it (`--provider openai-compatible --base-url URL`). It must work with a local Ollama server
> (the dev machine has `qwen3-coder:30b` running at `127.0.0.1:11434`), so the Phase 0 gate can be
> run with no API key, no spend and no consumer-subscription automation. The adapter maps messages,
> tool calls, tool results and usage to the existing `Model`/`Message`/`ModelReply` seam; tests are
> offline with an injected transport. Auth is optional only for a loopback base URL; a remote base
> URL requires a key from `ASSAY_API_KEY`. Keep Anthropic as the default provider. No new dependency.
> This partially covers the deferred "provider #2" nice-to-have and does not change any detection
> logic.

Source: direct user need after `M1.4`; the subscription route is forbidden by `CLAUDE.md`/R6, and a
local OpenAI-compatible server is the zero-key path.

## Context carried from the pick

- `CLAUDE.md` BYOK rule and `docs/ROADMAP.md` R6: no consumer-subscription automation. This slice
  does not touch that; it uses a local model server.
- `docs/technical/CAPABILITY_ROADMAP.md` A3 lists provider #2 as deferred; the `Model` protocol in
  `src/assay/agent/base.py` was designed for exactly this.
- `src/assay/agent/anthropic.py` is the reference adapter (transport injection, key handling, error
  mapping, 60 s timeout); `src/assay/cli/main.py` builds the model from `ANTHROPIC_API_KEY`.
- Ollama on the dev machine: version 0.40.10, model `qwen3-coder:30b`, OpenAI-compatible base
  `http://127.0.0.1:11434/v1`.
