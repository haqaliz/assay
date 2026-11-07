# Spec — `mcp-server` / `stage-a` (server record, runtime inspection, `assay mcp`)

Parent: `docs/planning/mcp-server/prd.md`. Stage A only; no driver or verdict.

## Problem slice

A user has a Claude Desktop-style `mcpServers` manifest. Stage A turns one selected stdio server
into a `Server` record, starts it in Seatbelt, performs `initialize` + `tools/list`, and prints a
`ServerReport`. It is a runtime inspector, not a verifier.

## In scope

- `src/assay/mcp/server.py` — `Server`, `ServerError`, `parse_server`.
- `src/assay/mcp/inspect.py` — `ServerReport`, `inspect_server`.
- `src/assay/cli/main.py` — `assay mcp <manifest>`.
- Tests: parser, inspect (fake + real macOS), CLI.
- Docs: PRD/spec/plan, ARCHITECTURE, CAPABILITY_ROADMAP, ROADMAP, README, CHANGELOG.
- No new dependency; no verdict/trace/schema/floor change.

## Out of scope

Driver/model, assessment/verdict, bundle, ServerTrace, HTTP/SSE/OAuth, registry/install, env values,
third-party servers, changes to A1–A8/A10.

## Contracts

### `Server`

```python
@dataclass(frozen=True, slots=True)
class Server:
    name: str
    command: str
    args: tuple[str, ...]
    source_path: Path
    source_hash: str  # sha256 of the manifest bytes, bare lowercase hex
    transport: str = "stdio"

class ServerError(ValueError): ...

def parse_server(path: Path, *, name: str | None = None) -> Server: ...
```

Manifest forms:

```json
{"mcpServers": {"demo": {"command": "python3", "args": ["-u", "server.py"]}}}
```
or

```json
{"command": "python3", "args": ["-u", "server.py"]}
```

Rules:

- `command` non-empty string (required).
- `args` absent → `()`; otherwise a list of strings.
- `env` absent or `{}` only; any non-empty mapping is refused (`no secrets in the jail`).
- any `url` key is refused (`stdio only`).
- `mcpServers`: select `--name`; if exactly one entry, default; zero/multiple without `--name` is a
  named error listing the names.
- single object: name = `--name` or the file stem.
- malformed JSON/shape is a `ServerError` with the path, never a traceback.
- `source_hash` covers the manifest bytes; values are never echoed.

### `ServerReport`

```python
@dataclass(frozen=True, slots=True)
class ServerReport:
    server: Server
    started: bool
    protocol_version: str | None
    tools: tuple[MCPTool, ...]
    session: SessionRecord | None
    error: str | None

def inspect_server(
    server: Server,
    *,
    run_root: Path,
    sandbox_exec: Path = Path("/usr/bin/sandbox-exec"),
    timeout: float = 10.0,
    keep: bool = False,
    session_factory: Callable[..., SandboxSession] = SandboxSession,
) -> ServerReport: ...
```

- Build `JailConfig(run_root=..., limits=Limits(wall_seconds=30, cpu_seconds=30), keep=keep)`.
- Spawn `SandboxSession(sandbox_exec, [command, *args], config)`.
- `MCPClient(session, timeout=timeout)`; `initialize()`; `list_tools()`.
- `started=True` once the handshake succeeds; a later `tools/list` failure sets `error`.
- `SandboxFailed`/`SessionError`/`MCPError`/`OSError` becomes a report error; the session is always
  closed and its record kept.
- No model, no assessment, no `Skill`.

### CLI

`assay mcp <manifest> [--name NAME] [--timeout SECONDS] [--json] [--keep-run-root]`

- No model/provider/price/cost flags.
- exit `0` iff `started` and `error is None`; `1` on startup/protocol failure; `2` on usage/manifest
  error.
- human output: server, command, transport, started, protocol, tool names, denials, error, and
  `inspection only; no verdict`.
- JSON output: `server` (name/command/args/transport/source_hash), `started`, `protocol_version`,
  `tools` (name/description/input_schema), `session` (exit/signal/timed_out/config_hash/denials/
  teardown_error), `error`. No verdict field.
- the run root is removed unless `--keep-run-root`.

## Test matrix

| Area | Test file | Offline? |
|---|---|---|
| Manifest parsing/selection/refusals/hash | `tests/test_mcp_server.py` | yes |
| Inspect success/failure/timeout with a fake session | `tests/test_mcp_inspect.py` | yes |
| Inspect the real fixture in Seatbelt | `tests/test_mcp_inspect.py` | macOS only |
| CLI success/failure/JSON/usage | `tests/test_cli_mcp.py` | macOS only (real sandbox) |

## Acceptance criteria

1. `parse_server` accepts both manifest forms, selects one server, computes the source hash and
   refuses missing command, URL, env, malformed JSON and bad arg types with `ServerError`.
2. `inspect_server` against the fixture returns `started=True`, protocol `2026-07-28`, four tools and
   a `SessionRecord`; a missing command/startup failure returns `started=False` with an error.
3. `assay mcp` prints the report and no verdict; exit 0/1/2 as above; JSON has no verdict key.
4. The fixture's outside-read denial is visible in the session record; no host data is read.
5. Full `uv run pytest` green; no new dependency; no `EventKind`/`Trace.schema`/`FindingClass`/
   floor/`REVIEW` cap change.
6. Docs say "inspector, not a verifier"; MCP remains a deferred capability with Stage B next.

## Risks

- Inspector exit 0 could be read as safe → output/docs say "inspection only; no verdict".
- Env refusal blocks servers that need keys → explicitly named; no secrets in the jail.
- Command/relative path may fail in the jail → report the failure; document the run-root rule.
- Stage B is a different surface → separate PRD; do not smuggle a verdict into Stage A.
