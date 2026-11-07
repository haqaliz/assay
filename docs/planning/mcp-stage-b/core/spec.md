# Spec — `mcp-stage-b` / `core` (driver registration + `mcp-report`)

Parent: `docs/planning/mcp-stage-b/prd.md`. Approved policy: **B — `mcp-report`**; exit `0` means
"report produced", not safe; verdict is `UNVERIFIED` or `FLAGGED`; no `CLEAN`/`MALICIOUS`.

## In scope

- `drive_with(system_prompt, task, ..., tools=TOOLS)` seam; `drive(skill, ...)` stays as a wrapper.
- `ToolExecutor` protocol.
- `MCPToolbox` in `src/assay/mcp/toolbox.py`.
- `ServerRun`/`ServerAssessment`/`assess_server` in `src/assay/mcp/assess.py`.
- `instruction_labels` helper in `src/assay/verdict/assess.py`.
- CLI `mcp-report` + renderer.
- Tests, docs.

## Out of scope

`CLEAN`/`MALICIOUS` for servers; full syscall mediation; signed server bundle/`ServerTrace`; HTTP/SSE/
OAuth; registry/install; resources/prompts/sampling/elicitation; built-in tools in the server run;
changes to the skill verdict contract/floor/`REVIEW` cap.

## Contracts

### Driver seam

```python
class ToolExecutor(Protocol):
    def execute(self, call: ToolCall) -> ToolResult: ...

def drive_with(
    system_prompt: str,
    task: str,
    model: Model,
    toolbox: ToolExecutor,
    budget: Budget,
    *,
    tools: Sequence[ToolSpec] = TOOLS,
    clock: Callable[[], float] = time.monotonic,
) -> RunOutcome: ...

def drive(skill: Skill, task: str, model: Model, toolbox: ToolExecutor,
          budget: Budget, *, clock: Callable[[], float] = time.monotonic) -> RunOutcome:
    return drive_with(skill.body, task, model, toolbox, budget, clock=clock)
```

- `drive_with` is the loop; `model.complete(messages, tools)` uses the supplied list.
- `drive` preserves the current API and `TOOLS`; existing tests unchanged.
- `check` continues to pass `skill.body`.

### `MCPToolbox`

```python
class MCPToolboxError(RuntimeError): ...

class MCPToolbox:
    def __init__(self, client: MCPClient, tools: Sequence[MCPTool]) -> None: ...
    @property
    def tools(self) -> tuple[ToolSpec, ...]: ...
    @property
    def events(self) -> tuple[Event, ...]: ...
    @property
    def findings(self) -> tuple[Finding, ...]: ...
    def execute(self, call: ToolCall) -> ToolResult: ...
```

- Spec name `mcp__<tool>`; original name ≤ 59 chars and `[A-Za-z0-9_-]+`; duplicates are
  `MCPToolboxError`.
- `ToolSpec.description` is the MCP description; `input_schema` is the MCP `inputSchema` (default
  `{"type": "object", "properties": {}}`, ensure `type` is present).
- `execute`: unknown name → `ToolResult(ok=False, output=...)`; known → `MCPClient.call_tool`;
  `MCPError` becomes a failed `MCPResult`; one `event_for_call` per call.
- Scan each tool description and each result text with `instruction_labels`; one
  `Finding(INSTRUCTIONS, REVIEW, target="tool:<name>"|"result:<name>",
  reason="... matches <label>", outcome=OK, review_required=True)` per label, deduped.
- No built-in tools; `ToolResult.record=None`.

### `ServerRun` / `ServerAssessment`

```python
@dataclass(frozen=True, slots=True)
class ServerRun:
    server: Server
    task: str
    tools: tuple[MCPTool, ...]
    events: tuple[Event, ...]
    findings: tuple[Finding, ...]
    outcome: RunOutcome
    session: SessionRecord
    @property
    def task_hash(self) -> str: ...

@dataclass(frozen=True, slots=True)
class ServerAssessment:
    server_name: str
    source_hash: str
    task_hash: str
    verdict: Verdict
    cause: UnverifiedCause | None
    findings: tuple[Finding, ...]
    strictness: Strictness
    blocked: bool
    def to_payload(self) -> dict[str, object]: ...

def assess_server(run: ServerRun, *, policy: StrictnessPolicy = DEFAULT_POLICY) -> ServerAssessment: ...
```

Policy (B):

| Condition | Verdict | Cause |
|---|---|---|
| `outcome.cause == cost-capped` | `UNVERIFIED` | `COST_CAPPED` |
| `outcome.cause in (step/action/wall limit)` | `UNVERIFIED` | `BUDGET_LIMIT` |
| any other `outcome.cause` | `UNVERIFIED` | `AGENT_FAILED` |
| findings (and no cause) | `FLAGGED` | — |
| no findings, no `TOOL` events | `UNVERIFIED` | `NO_TRIGGER` |
| no findings, calls present | `UNVERIFIED` | `NO_DECLARED_SCOPE` |

- `ServerAssessment` rejects `CLEAN`/`MALICIOUS`; `UNVERIFIED` iff cause; `FLAGGED` needs findings
  and no `HIGH`.
- `blocked`: `STANDARD` → any finding; `STRICT` → any finding or `UNVERIFIED`; `BASELINE` → any
  `HIGH` (none in Stage B).
- `task_hash`/`source_hash` are 64 lowercase hex.

### CLI `mcp-report`

`assay mcp-report <manifest> --task TEXT [--name] [--timeout] [--model ...] [--provider ...]
[--base-url] [--api-key] [--input-price] [--output-price] [--max-cost] [--max-steps]
[--max-actions] [--max-wall-seconds] [--strictness] [--out PATH] [--json] [--keep-run-root]`

- `--task` required; `--model`/prices/`--max-cost` use the `check` validation.
- Startup/tools failure → error, exit `1`; usage/manifest → `2`.
- Run cause (`agent-failed`/`budget`/`cost`) → exit `1`.
- Otherwise → exit `0` (report produced; `UNVERIFIED` or `FLAGGED`, never a pass).
- JSON includes: server, task hash, tools, events, session (no raw stderr), findings, verdict/cause/
  blocked/strictness, note `observation report; not a pass; no CLEAN/MALICIOUS`, exit.
- Human output has the same and no `CLEAN`/`MALICIOUS` claim.
- Optional `--out PATH` writes the JSON report.

## Test matrix

| Area | Test file | Offline? |
|---|---|---|
| `drive_with` custom prompt/tools; `drive` unchanged | `tests/test_agent_driver.py` | yes |
| `MCPToolbox` namespace/calls/events/findings/refusals | `tests/test_mcp_toolbox.py` | yes |
| `assess_server` verdicts/causes/blocked/no CLEAN | `tests/test_mcp_assess.py` | yes |
| CLI `mcp-report` with a scripted model + real fixture | `tests/test_cli_mcp_report.py` | macOS only |
| Full regression | `uv run pytest` | — |

## Acceptance criteria

1. `drive_with` uses the supplied system prompt and tools; `drive(skill, ...)` still passes all
   existing tests.
2. `MCPToolbox` exposes `mcp__<tool>` specs, calls the MCP client, records one TOOL event per call,
   and creates `INSTRUCTIONS/REVIEW` findings from descriptions/results (deduped).
3. `assess_server` returns only `UNVERIFIED`/`FLAGGED`; no `CLEAN`/`MALICIOUS`; causes as above.
4. `mcp-report` with a scripted fake model and the real fixture produces a report with a call event,
   no verdict overclaim, exit 0; a model failure exits 1; a startup failure exits 1; a malformed
   manifest exits 2.
5. No new dependency; no `Trace`/bundle/`ServerTrace`; no floor/`REVIEW` cap change.
6. Docs: spec/plan, ARCHITECTURE, CAPABILITY_ROADMAP, ROADMAP, README, CHANGELOG.

## Risks

- Exit 0 is not a pass → output note/docs; no `CLEAN`/`MALICIOUS`.
- No mediation → no `MALICIOUS`; say so.
- Instruction false positives → existing cap; one finding per label/target.
- Driver refactor regression → wrapper + full suite.
- Task quality → required `--task`, hash recorded.
