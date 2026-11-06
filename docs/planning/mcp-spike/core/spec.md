# Spec — `mcp-spike` / `core` (sandbox session + stdio MCP client)

Parent: `docs/planning/mcp-spike/prd.md`. This is the spike slice only; no MCP verdict.

## Problem slice

A long-lived stdio MCP server must run inside the Seatbelt jail, answer `initialize`, `tools/list`
and `tools/call`, and leave evidence as `EventKind.TOOL` events. The current `SeatbeltSandbox.run`
is one-shot, blocks on exit, and deletes the root. The spike adds a session and a stdlib client
without changing the trace schema or verdict contract.

## In scope

- `src/assay/sandbox/session.py` — `SandboxSession`, `SessionRecord`, `SessionError`,
  `SessionTimeout`, `SessionClosed`.
- `src/assay/mcp/client.py` — `MCPClient`, `MCPTool`, `MCPResult`, `MCPError`, `MCPTimeout`,
  `MCPProtocolError`.
- `src/assay/mcp/events.py` — `event_for_call`.
- `tests/fixtures/mcp_server.py` — stdlib fixture server (`echo`, `read_inside`, `read_outside`,
  `slow`).
- Tests: offline client/framing/session lifecycle, real macOS confinement, TOOL-only verdict.
- Docs: this spec/plan, a short ARCHITECTURE note, CHANGELOG `Unreleased`, roadmap status.

## Out of scope

Manifest parser, `Server` record, `Skill`/`Trace`/bundle integration, driver/dynamic tools, MCP
verdict policy, HTTP/SSE/OAuth, registry/CLI, installing third-party servers, changes to the floor,
`REVIEW` cap, `Trace.schema`, `FindingClass`, or `EventKind`.

## Contracts

### `SandboxSession`

```python
@dataclass(frozen=True, slots=True)
class SessionRecord:
    exit_code: int | None
    signal: int | None
    stderr: str
    truncated: bool
    denials: tuple[DenialRecord, ...]
    config_hash: str
    run_root: str
    timed_out: bool
    teardown_error: str | None = None

class SessionError(RuntimeError): ...
class SessionClosed(SessionError): ...
class SessionTimeout(SessionError, TimeoutError): ...

class SandboxSession:
    def __init__(self, sandbox_exec: Path, argv: Sequence[str], config: JailConfig,
                 *, max_line_bytes: int = 1_048_576) -> None: ...
    def __enter__(self) -> "SandboxSession": ...
    def __exit__(self, *exc: object) -> None: ...
    def write_line(self, line: str) -> None: ...
    def read_line(self, deadline: float) -> str: ...
    def close(self) -> SessionRecord: ...
    @property
    def record(self) -> SessionRecord | None: ...
    @property
    def pid(self) -> int: ...
```

- Spawn: `sandbox-exec -p <profile> <argv...>`, `stdin/stdout/stderr=PIPE`, `cwd=run_root`,
  `start_new_session=True`, `preexec_fn=_limit_setter(limits)`.
- stdout reader thread: one line per `readline(max_line_bytes + 1)`; a line longer than the cap
  raises `SessionError`; EOF puts a sentinel.
- stderr drain thread: chunks into a bounded buffer (`OUTPUT_CAP_BYTES`); never merged with stdout.
- `read_line(deadline)` uses the queue with the remaining time; `SessionTimeout` on expiry.
- A dead process raises `SessionClosed`; a `sandbox-exec` failure (exit 65/71 or stderr prefix)
  raises `SandboxFailed` with the stderr excerpt.
- `close()` closes stdin, `killpg`s the group, waits, joins both threads, closes pipes, removes the
  run root unless `keep=True`, and returns the `SessionRecord`. Idempotent.
- No unconfined fallback.

### `MCPClient`

```python
PROTOCOL_VERSION = "2026-07-28"  # pinned to the fixture; provisional
MAX_LINE_BYTES = 1_048_576

@dataclass(frozen=True, slots=True)
class MCPTool:
    name: str
    description: str
    input_schema: Mapping[str, object]

@dataclass(frozen=True, slots=True)
class MCPResult:
    ok: bool
    text: str
    raw: Mapping[str, object] | None = None

class MCPClient:
    def __init__(self, session, *, timeout: float = 10.0) -> None: ...
    def initialize(self) -> Mapping[str, object]: ...
    def list_tools(self) -> tuple[MCPTool, ...]: ...
    def call_tool(self, name: str, arguments: Mapping[str, object] | None = None) -> MCPResult: ...
    def close(self) -> None: ...
    def __enter__(self) -> "MCPClient": ...
    def __exit__(self, *exc: object) -> None: ...
```

- Newline-delimited JSON-RPC 2.0; one object per line; `json.dumps(..., separators=(",", ":"),
  ensure_ascii=False)`.
- `initialize`: `protocolVersion`, empty `capabilities`, `clientInfo={"name":"assay","version":...}`;
  then `notifications/initialized`.
- `tools/list`: first page; map `name`, `description`, `inputSchema`.
- `tools/call`: concatenate `content[].text`; `isError` → `MCPResult.ok=False`; JSON-RPC `error` →
  `MCPError`.
- Id correlation: ignore notifications; an unmatched id is a protocol error; malformed JSON and
  non-object messages are `MCPProtocolError`.
- Per-request deadline; `SessionTimeout`/`TimeoutError` → `MCPTimeout`.
- No sampling/elicitation/pagination/HTTP.

### Evidence

```python
def event_for_call(tool: str, arguments: Mapping[str, object], result: MCPResult,
                   *, denials: Sequence[str] = ()) -> Event: ...
```

- `EventKind.TOOL`; `target=tool`; `request="tools/call"`.
- `input_sha256` = SHA-256 of canonical JSON arguments.
- `content_sha256`/`content_bytes` over the UTF-8 result text; `excerpt` first 4096 bytes;
  `truncated` when longer.
- `outcome`: `DENIED` if denials, else `OK` if `result.ok`, else `FAILED`.
- No new `EventKind`; no `Trace`/`Server` identity.

## Fixture server

`tests/fixtures/mcp_server.py`, staged into the run root and run as
`/usr/bin/python3 -u mcp_server.py`:

- `echo` → `{"text": ...}`.
- `read_inside` → reads a relative path under the run root.
- `read_outside` → attempts `/private/etc/hosts`; prints `assay-denial: file-read ...` to stderr and
  returns `isError`.
- `slow` → sleeps 5s (timeout test).
- stdout is protocol-only; stderr diagnostics only.

## Acceptance criteria

1. Offline: `MCPClient` with a fake session performs the handshake, lists tools, calls a tool,
   concatenates text, handles `isError`, JSON-RPC errors, malformed lines, unmatched ids and
   timeouts. No process, model or network.
2. Offline: `SandboxSession` with a fake `sandbox-exec` script (drops `-p <profile>` and execs the
   rest) writes/reads lines, times out, closes idempotently, kills the process group and returns a
   `SessionRecord`.
3. Real macOS: the fixture server runs inside Seatbelt; `initialize`/`tools/list` succeed;
   `echo`/`read_inside` succeed; `read_outside` is denied and the denial is in stderr; `slow` times
   out; `close()` leaves no child (`os.kill(pid, 0)` raises).
4. A TOOL-only `Trace` is `UNVERIFIED/NO_TRIGGER` with no findings; `diff` ignores TOOL; no
   `EventKind`/`Trace.schema`/`FindingClass`/floor change.
5. Full `uv run pytest` green; no new dependency; offline tests do not need a model or network.
6. Docs: ARCHITECTURE note (evidence-only), CHANGELOG `Unreleased`, roadmap status. No README "MCP
   supported" claim.

## Test matrix

| Area | Test file | Offline? |
|---|---|---|
| JSON-RPC framing, id, errors, timeout | `tests/test_mcp_client.py` | yes |
| Session lifecycle, fake sandbox | `tests/test_sandbox_session.py` | yes |
| Event mapping | `tests/test_mcp_events.py` | yes |
| TOOL-only verdict | `tests/test_mcp_events.py` | yes |
| Real session + confinement | `tests/test_mcp_session_real.py` | macOS only |

## Risks

- Protocol version churn: pinned `2026-07-28`; fixture only; no `server/discover`.
- Pipe buffering: fixture `-u`; line cap; reject non-JSON.
- stderr deadlock: drain thread.
- Orphan: `start_new_session` + `killpg`; close test.
- Cumulative `RLIMIT_CPU`: documented; per-request deadline only.
- No verdict: evidence-only; do not fake a `Skill`/`Server`.
