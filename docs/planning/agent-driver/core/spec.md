# Spec — `agent-driver` / `core` (A3)

## Problem slice & user outcome

Given a parsed `Skill`, a task string, a `Model` and a `Toolbox`, run a bounded agent loop in which
the model's tool calls are executed inside the A2 sandbox and return a `RunOutcome` (actions,
transcript, usage, cost, named stop cause). Never assigns a verdict; never lets the API key reach
the jail; never makes a network or model call in tests.

## In scope

- `Usage`, `ModelPrice`, `Budget`, `ToolCall`, `ToolResult`, `ToolAction`, `RunCause`, `RunOutcome`,
  `AgentError`, `AgentUnavailable`, `ModelFailed`.
- `Model` protocol + `ModelReply` + provider-neutral `Message`; `AnthropicModel` over stdlib HTTP
  with an injected transport; `from_env`.
- `Toolbox` with `read_file`, `write_file`, `run_shell`, `http_get`; one `Sandbox.run` per action;
  argument validation; payload/output caps; per-tool network policy.
- `task_for(skill)` deterministic single task.
- `drive()` with step / cost / wall limits and named causes.
- Offline tests, plus one `darwin`-gated real-confinement toolbox test.

## Out of scope

A4 capture/diff, A5 verdicts, CLI, provider #2, streaming, retries, LLM task planning, multi-task
runs, MCP.

## Acceptance criteria

1. `Usage` adds token-wise; `ModelPrice.cost(usage)` = `in/1e6*price.in + out/1e6*price.out`; negative
   or bool prices are rejected; `Budget` requires positive `max_usd`, `max_steps>=1`,
   `max_wall_seconds>0`.
2. `RunCause` is the closed set `{MISSING_KEY, MODEL_FAILED, COST_CAPPED, STEP_LIMIT, ACTION_LIMIT,
   WALL_LIMIT, SANDBOX_UNAVAILABLE}`; `RunOutcome.finished` is true only when `cause is None and
   final_text is not None`.
3. `Toolbox.execute` maps each tool to exactly one `Sandbox.run`:
   - `read_file` → `/bin/cat <path>`, no network
   - `write_file` → content staged under `run_root/.assay-io/`, `/bin/cp <staged> <path>`, no network
   - `run_shell` → `/bin/sh -c <command>`, no network
   - `http_get` → `/usr/bin/curl -sS --max-time 10 <url>`, `allow_network=(NetRule("*",80), NetRule("*",443))`
   All other calls get `allow_network=()`.
4. Every `JailConfig` the toolbox builds has `env == {}` (no model credential) and
   `run_root == toolbox.run_root`.
5. Invalid arguments (missing key, non-string, empty), unknown tool, or `write_file` content over
   `MAX_TOOL_PAYLOAD_BYTES` return `ok=False` **without** running the sandbox and without raising.
6. A failed/denied `RunRecord` yields `ok=False` and keeps the record (with its `DenialRecord`s).
7. `task_for(skill)` is deterministic (same skill → identical string), includes `skill.name` and
   `skill.description`, instructs the model to use tools and end with a summary, and does not repeat
   `skill.body` (that is the system prompt).
8. `AnthropicModel.from_env` with no `ANTHROPIC_API_KEY` raises `AgentUnavailable` with
   `cause=MISSING_KEY` before any transport call.
9. `AnthropicModel.complete` posts JSON containing `model`, `max_tokens`, `system` (skill body mapped
   from the system message), `messages`, `tools`; headers carry `x-api-key`, `anthropic-version`,
   `content-type`; the key never appears in the body.
10. The adapter parses `text` blocks, `tool_use` blocks (id/name/input) and usage; HTTP/transport
    errors and malformed JSON raise `ModelFailed`.
11. `drive()` with a fake model performs `tool call → tool result → answer` and returns
    `cause=None`, `final_text` set, `steps==2`, actions in order.
12. `drive()` refuses a call whose worst-case cost would cross `max_usd` before making it, and stops
    with `COST_CAPPED` when a reply still crosses it; `STEP_LIMIT` at `max_steps`; `ACTION_LIMIT` at
    `max_actions`; `WALL_LIMIT` when elapsed exceeds the budget; `MODEL_FAILED` when the model fails;
    `SANDBOX_UNAVAILABLE` when the sandbox disappears mid-run. In every case the actions so far are
    returned, not an exception.
13. Every executed action's `JailConfig.env` contains no `ANTHROPIC_API_KEY` (asserted over the
    captured configs).
14. Real confinement (`darwin` only): through `Toolbox`, a write inside the run root succeeds and a
    write to `../escape.md` is denied and captured as a non-ok action.

## Dependencies & sequencing

A1 and A2 are merged and stable. Consumes `Sandbox`, `JailConfig`, `NetRule`, `Limits`, `RunRecord`
from `assay.sandbox`, and `Skill` from `assay.ingest`. No new dependency.

## Open questions / risks

- One deterministic task will often exercise nothing (R1). Accepted; the cause surfaces as
  `NO_TRIGGER` at A5, never `CLEAN`.
- `http_get` is port-scoped only (Seatbelt limit). Documented R4 weakening.
- `curl` presence is required for `http_get`; absence is `AgentUnavailable`, checked at `Toolbox`
  construction.
