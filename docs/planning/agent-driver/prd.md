# PRD — `agent-driver` (A3: agent driver, BYOK)

Status: draft for review. Date: 2026-10-29.
Pipeline position: A3 of `docs/technical/CAPABILITY_ROADMAP.md`; depends on A1 (merged) and A2
(merged). Feeds A4 (capture + diff) and, through it, the Phase 0 gate.

## Problem statement

A1 produces a declared scope; A2 can confine a command. Nothing yet makes a real agent *use* a
skill so there is behavior to observe. Without A3 the Phase 0 gate ("one real skill run end to
end, with an observed behavior that differs from a declared one") cannot be attempted, and A4 has
no event source to capture.

For whom: Assay itself (A4 consumes the run outcome), and the future `assay check` user who
supplies a BYOK key and pays for the run.

## Goals and success metrics

| Goal | Metric |
|---|---|
| A model drives a multi-step run offline | 3 scripted turns (tool call → tool call → answer) produce a finished outcome, every action executed through the injected sandbox |
| The key never enters the jail | Asserted: the `JailConfig.env` of every tool action contains no `ANTHROPIC_API_KEY` and no other model credential |
| Cost is bounded before it is spent | A call whose worst case would cross `max_usd` is refused before it is made (`COST_CAPPED`); a reply that still crosses it stops the run immediately |
| Every floor class is reachable | The four tools are always offered: `read_file`, `write_file`, `run_shell`, `http_get` |
| The evidence channel is not child-writable | The jail denies the child writes to `.assay/*`, so a shell command cannot truncate or forge its own capture (A2 change) |
| Sandbox loss is named | `SandboxUnavailable` mid-run becomes `cause=SANDBOX_UNAVAILABLE`, never a silent finish |
| Offline always | `uv run pytest` makes no model call and no non-loopback network call; the real provider path is exercised through an injected transport |
| No subscription automation | Only `ANTHROPIC_API_KEY` is read; absence is a named refusal, never a fallback to a logged-in CLI session |

Not a goal: any verdict, diff, trace format, CLI, or a second provider.

## Users and scenarios

1. **A4/A5** — take `RunOutcome.actions`, each with the model's request and the sandbox `RunRecord`,
   and diff the observed file/shell/network actions against `Skill.scope`.
2. **The maintainer running the Phase 0 gate** — parses a real Plumb skill, runs `drive()` with
   their own key, sees a real observation. This is a manual step (no key in CI).
3. **A skill author later (M1.4 CLI)** — reuses the same driver; A3 exposes no CLI.

## Requirements

### Must have

1. **Layering**: the model call happens in Assay's process (outside the jail); every tool action
   runs inside the A2 sandbox, one `Sandbox.run` per action, sharing a single per-run `run_root`.
   The key is therefore never available to the tested skill.
2. **`Model` seam**: `complete(messages, tools) -> ModelReply`, where `ModelReply` carries text,
   zero or more tool calls, and `Usage(input_tokens, output_tokens)`. Tests use a scripted fake;
   no mock framework.
3. **Anthropic adapter**: `AnthropicModel(model, api_key, price, transport=urlopen)` posts to the
   Messages API with `system = skill.body`, `tools` = the four tool schemas, and the running
   transcript. The key goes in the `x-api-key` header only. A missing key raises
   `AgentUnavailable(MISSING_KEY)` before any call. `model` and `price` are explicit arguments, no
   silent default (`docs/ROADMAP.md` R5: cost shown before the run).
4. **`Budget`**: `max_steps` (default 20), `max_actions` (default 40), `max_usd` (required,
   explicit), `max_wall_seconds` (default 300). Before each model call the driver estimates the
   worst-case cost (serialized input/4 tokens plus `max_tokens` output) and refuses to start a call
   that would cross `max_usd`. `COST_CAPPED`, `STEP_LIMIT`, `ACTION_LIMIT` and `WALL_LIMIT` stop the
   run with the actions so far in the outcome.
5. **Tools, always all four** (declared scope never filters them, or undeclared use could not be
   observed):
   - `read_file(path)` → `/bin/cat path` in the jail.
   - `write_file(path, content)` → content staged in a parent-owned directory outside the run
     root (read-only inside the jail), then `/bin/cp -- <staged> <path>` in the jail.
   - `run_shell(command)` → `/bin/sh -c command` in the jail.
   - `http_get(url)` → `/usr/bin/curl -sS --max-time 10 --url <url>` in the jail, with per-call
     `allow_network=(NetRule("*",80), NetRule("*",443))`; no other tool gets network. Only
     `http`/`https` are accepted, the host is resolved in the parent and passed as `--resolve`
     (the jail allows TCP but not DNS), and `/private/etc/ssl` is readable so TLS can start.
   Paths are relative to `run_root` by contract (the child's cwd); absolute paths may be attempted
   and the jail decides.
6. **`Toolbox`**: owns `run_root`, sanitises the run root (must be a real directory), enforces a
   `MAX_TOOL_PAYLOAD_BYTES` (1 MB) on `write_file` content and on returned output (A2 already caps
   output at 1 MB), and returns a `ToolResult` with `ok`, `output`, and the `RunRecord`.
7. **Deterministic task**: `task_for(skill)` builds one task from name + description,
   instructing the model to carry out the skill's stated purpose on a small self-chosen example and
   finish with a summary. The body is the system prompt and is not repeated in the task. No second
   model call, no randomness.
8. **`drive()`**: loops model → tool calls → results until a reply with no tool calls, a budget
   cause, or a model error. Returns `RunOutcome` with `cause: RunCause | None`, `final_text`,
   `steps`, `actions`, `usage`, `cost_usd`. A model/API error becomes `cause=MODEL_FAILED` and a lost
   sandbox becomes `cause=SANDBOX_UNAVAILABLE`; neither is an exception to a caller that asked for
   a run record (construction/config errors still raise). Tool output sent back to the model is
   truncated to 16k characters so the transcript cannot grow unbounded.
9. **Determinism boundary**: the agent is non-deterministic; the unit A4 replays is the recorded
   outcome, not a re-run (`ARCHITECTURE.md`). A3 must not pretend otherwise in names or docs.

### Should have

10. `AnthropicModel.from_env(model, price)` reading `ANTHROPIC_API_KEY`, so the manual gate run is
    one line.
11. One retry on HTTP 429/5xx with a short fixed backoff, counted against the budget's wall clock
    and reported in the outcome. (Only if it does not delay this slice; otherwise deferred.)

### Nice to have (deferred)

Streaming, prompt caching, provider #2, LLM-generated task lists, per-task token caps, MCP tools.

## Technical considerations

- **`http_get` weakens the jail by port, not host.** Seatbelt cannot pin a hostname
  (`docs/planning/sandbox-jail/understanding.md`), so a tested skill can reach any host on 80/443.
  The parent resolves the URL host (`getaddrinfo`) and passes `--resolve` because the jail allows
  TCP but not DNS; the URL must be `http`/`https`, which also stops curl option injection. Only
  `/private/etc/ssl` is re-allowed so TLS can start. Mitigation, stated honestly: no credentials are
  in the jail, only the run root is readable outside the deny-list, and A4 records the host so an
  undeclared call becomes a finding. This is R4 accepted for the network tool alone.
- **One sandbox run per action** costs ~tens of ms; acceptable for ≤20 steps and it gives A4 one
  `RunRecord` per action by construction (the mediated surface A2's deep dig called for).
- **Staged `write_file` content lives outside the run root** in a parent-owned directory that the
  jail may only read. Staging inside the root let a `run_shell` symlink redirect a parent-side write
  onto the host; that class is closed. The target write is still performed and judged by the jail.
- **The capture channel is no longer child-writable.** A2 now denies `file-write*` on
  `<run_root>/.assay`, so `run_shell` cannot truncate or forge the stdout/stderr the denials are
  classified from. `RunRecord.denials` kind for mediated writes is still heuristic (`cp` reports
  only `EPERM`), so A4 must classify by the tool call, not by the kind.
- **Cost arithmetic** is `usage × price` with prices supplied explicitly (`ModelPrice` in USD per
  million input/output tokens). Prompt caching is not enabled, so cache-token fields are ignored
  rather than silently priced wrong.
- **Layout**: `src/assay/agent/{records,base,anthropic,tools,tasks,driver,__init__}.py`, mirroring
  `sandbox/` (`records` = data, `base` = protocol, backend file, entry point).
- **Tests offline**: `tests/test_agent_{driver,tools,anthropic,tasks}.py`; a real-confinement
  toolbox test is `darwin`-gated like A2's suite. Anthropic tests inject a transport callable and
  assert the JSON body and headers; no sockets.
- **No new dependency**: `urllib.request` for the API, `/bin/cat`, `/bin/cp`, `/bin/sh`, `curl`
  are platform tools. `curl` presence is checked and a missing one is `AgentUnavailable`.

## Risks and open questions

| Risk | L/I | Mitigation |
|---|---|---|
| R1: one deterministic task will not trigger conditional behavior; runs will often be `UNVERIFIED` | High/High | Accepted and made explicit: A3 makes no verdict, `NO_TRIGGER` is A5's honest outcome. Task strategy is a seam for a later slice |
| R5: the user's key spends real money | High/Med | `max_usd` required; worst-case cost estimated before each call; tool output truncated to 16k chars; action cap; no default model or price |
| R4: `http_get` can reach any host on 80/443 | Low/Critical | No credentials in the jail, host recorded per action, port-only rule documented; the alternative is no network finding class |
| R6: someone points this at a subscription | Med/High | Only `ANTHROPIC_API_KEY` is read; no CLI-session path exists in the code |
| A model calls a tool with a path that escapes the run root | Low/High | The jail decides; denial lands in the action's `RunRecord` and is returned to the model as a failure |
| Non-deterministic cost makes tests flaky | Med/Med | Fake model returns fixed usage; real adapter tests assert arithmetic, not live prices |
| Prompt injection in the skill body manipulates the agent | High/Med | That is a *finding*, not a driver failure: A4/A5 own instruction-injection detection. A3 must pass the body as data and must not let it change the tool set or the budget |

Open questions:
- Exact model id for the manual gate run: whichever the user's key can call; nothing is hardcoded.
- Should `drive()` accept multiple tasks per skill now? No: one run, one task, one outcome. Multi-task
  runs belong with A7's benchmark.

## Out of scope

- A4 trace format, event capture, diff, corpus.
- A5 verdicts, strictness, the floor.
- CLI, config files, defaults for model or price.
- Streaming, retries beyond one, provider #2, LLM task planning, MCP, memory, multi-turn chat beyond
  one task.

## Areas to strengthen before sharing (self-critique)

- 🟡 The tool schemas are hand-written Anthropic JSON; the adapter test asserts the shape we send,
  not that Anthropic accepts it. The manual gate run is the only real proof, and it needs a key.
- 🟡 `write_file` staging is a parent-side write; it now happens outside the run root in a
  parent-owned directory the jail may only read, so the child cannot redirect it with a symlink. The
  staged payload contains only content the model produced.
- 🟡 Real `http_get` was verified once by hand (`https://example.com` → 200). It is not covered by an
  automated real-network test because the suite is offline; a loopback test needs a privileged port.
- 🔴 The Phase 0 gate still needs A4: A3 produces actions, not a finding. Do not call the gate passed
  after A3 alone.
- Question before greenlighting: **with one deterministic task and a 20-step cap, what fraction of
  the 10 Plumb skills do we expect to actually exercise file/network/shell behavior, and is that
  enough to prove the wedge in Phase 0, or should the first slice ship two or three fixed task
  templates instead of one?**
