# PRD — `mcp-server` (Stage A: server record + runtime inspection; Stage B: driver/verdict)

Status: proposed, 2026-11-07. Stage A to build now; Stage B needs its own spec.
Parent: `docs/planning/mcp-design/prd.md` and the merged MCP spike (`docs/planning/mcp-spike/`).

## Problem

The spike proves the transport: a stdio server runs in Seatbelt and Assay can initialize, list tools
and call one. It has no server identity, no manifest, no startup report, no driver integration and no
server verdict. A user cannot yet point Assay at an MCP server and see what happened.

A manifest alone is not verification: it declares startup, not behavior. Stage A therefore pairs a
manifest with a real startup and tool discovery, and reports evidence without a verdict. Stage B can
then add the driver and a conservative assessment.

## Scope tree

```
MCP server
├─ Stage A (build now)
│  ├─ Server record + mcpServers/stdin manifest (stdio only)
│  ├─ startup + initialize + tools/list inside Seatbelt
│  ├─ ServerReport (startup, protocol, tools, denials, session)
│  └─ `assay mcp <manifest>` — no model, no verdict
└─ Stage B (next PRD)
   ├─ register MCP tools with the driver
   ├─ derive/accept a task; capture tools/call
   └─ conservative assessment (no CLEAN; UNVERIFIED by default)
   ✗ HTTP/SSE/OAuth
   ✗ registry / install
   ✗ bundle / ServerTrace schema
```

## Goals and success metrics

### Stage A

| Goal | Metric |
|---|---|
| A server has a typed identity | Parse a Claude Desktop-style `mcpServers` manifest into a `Server` (name, command, args, source hash); reject missing command, URL transport, and env values |
| Startup is real | Start the command in a `SandboxSession`; `initialize` and `tools/list` succeed against a local fixture |
| Evidence is visible | `ServerReport` carries protocol version, tools, session record, denials and a named error on failure |
| No false verdict | `assay mcp` prints an inspection and exits without an `Assessment`; no `CLEAN`/`FLAGGED`/`MALICIOUS` |
| Secrets stay out | A manifest with a non-empty `env` is refused before spawn; values are never recorded |
| No new dependency | Manifest/client/report use the stdlib and the merged spike |

### Stage B (deferred; metrics to be set in its PRD)

- The model can call MCP tools alongside the four built-ins; each call is TOOL evidence.
- A server run never claims `CLEAN` from the manifest; the default is `UNVERIFIED`.
- The floor, `REVIEW` cap and trace schema are unchanged.

## Users and scenarios

1. **User** — runs `assay mcp server.json` to see whether a server starts, what tools it exposes and
   what the jail denied. No safety claim.
2. **Maintainer** — gets a `Server` record and report as the base for Stage B.
3. **Registry/CI (future)** — can run the inspector as a smoke check, not a verdict.

## Stage A requirements

### Must have

1. **`Server` record** in `src/assay/mcp/server.py`:
   ```python
   @dataclass(frozen=True, slots=True)
   class Server:
       name: str
       command: str
       args: tuple[str, ...]
       source_path: Path
       source_hash: str  # sha256 of the manifest bytes, bare hex
       transport: str = "stdio"
   ```
2. **Manifest parser**:
   - accepts `{"mcpServers": {"<name>": {"command": ..., "args": [...], "env": {...}}}}` and a
     single server object `{"command": ..., "args": [...]}`;
   - `--name` selects one; exactly one server is the default; zero/multiple without `--name` is a
     named error;
   - `command` must be a non-empty string; `args` a list of strings;
   - `url`/HTTP transport is refused (`stdio only`);
   - any non-empty `env` is refused (`no secrets in the jail`); do not record values;
   - malformed JSON/shape is a named refusal, not a traceback.
3. **`inspect_server`** in `src/assay/mcp/inspect.py`:
   - build a `JailConfig` and a `SandboxSession` for `[command, *args]`;
   - `MCPClient.initialize()` then `tools/list`; close the session;
   - return `ServerReport` with `started`, `protocol_version`, `tools`, `session`, `error`;
   - a missing command, `SandboxFailed`, `MCPError` or timeout is captured as a report error and a
     non-zero CLI exit; no partial success is reported as success;
   - injectable `session_factory` for offline tests.
4. **CLI** `assay mcp <manifest>`:
   - options `--name`, `--timeout`, `--json`, `--keep-run-root`;
   - no model, provider, price or cost flags;
   - human output: server, command, protocol, tool names, denials, error;
   - JSON output: the report payload;
   - exit `0` when the server started and tools were listed; `1` on startup/protocol failure;
     `2` on usage/manifest error;
   - the output never says `CLEAN`, `FLAGGED`, `MALICIOUS` or "safe".
5. **Tests**:
   - parser: `mcpServers`, single object, selection, missing command, URL refusal, env refusal,
     malformed JSON, source hash;
   - inspect: fake session factory covers success, startup failure, timeout, tools list; real macOS
     test with the fixture manifest; no model/network;
   - CLI: success/failure/usage with an injected inspect function or a temp manifest; JSON shape.
6. **Docs**: this PRD, `core/spec.md`, `core/plan_*.md`, ARCHITECTURE, CAPABILITY_ROADMAP,
   ROADMAP, README ("not a verifier"), CHANGELOG `Unreleased`.
7. **No new dependency; no verdict/trace/schema/floor change.**

### Should have

8. A manifest fixture under `tests/fixtures/` and a CLI smoke test.
9. A `ServerReport` that is stable enough to become the input to Stage B.
10. A clear "inspection, not a verdict" banner in human output.

### Nice to have (deferred)

- HTTP/SSE transport, auth, registry, install, bundle, `Server` trace, driver, verdict.

## Stage B design sketch (not built)

- Extend `Toolbox`/`drive` with an optional MCP client and tool specs; namespace MCP tools to avoid
  collisions; allow a user-supplied task; capture each `tools/call` as `EventKind.TOOL`.
- The manifest has no file/network/tool behavior declaration, so the default verdict is
  `UNVERIFIED`. There is no `CLEAN` from startup. A captured `HIGH` action from the agent's own
  built-in tools can still be `MALICIOUS`; the floor and cap do not move.
- The `Server`/trace/bundle identity needs a separate design; do not fake a `Skill`.

## Technical considerations

- **Why a runtime inspector, not a manifest parser.** Parsing alone is the static-scan trap. Stage A
  starts the server and lists tools; the report says what happened, not whether it is safe.
- **Why refuse `env`.** A manifest env often carries API keys. Passing them into the jail would put
  real secrets in an untrusted process; recording them would leak. Stage A supports servers that need
  no env values and names the refusal. A later slice can add an explicit, redacted env mechanism.
- **Command resolution.** `SandboxSession` runs with `DEFAULT_PATH`; a command resolved from the
  user's shell may be outside the jail. The report must show the failure, not bypass the jail.
- **Relative args.** The session's cwd is a fresh run root. A server script must be installed on the
  jail PATH or copied into the run root; Stage A documents this and does not add the manifest
  directory to `allow_read_extra`.
- **Exit codes.** The inspector's `0` means "started and listed tools", not "safe". The docs and
  output say so.

## Risks and open questions

| Risk | L/I | Mitigation |
|---|---|---|
| Users read inspect `0` as a verdict | High/High | No verdict words; banner; docs; exit code is inspection only |
| Env refusal blocks common servers | High/Med | Name the refusal; add a safe env slice later |
| Command/relative-path confusion | Med/Med | Report the failure; document the run-root rule |
| Manifest format drift | Med/Med | Claude Desktop `mcpServers` + single object; stdio only |
| Stage B verdict ambiguity | High/High | Separate PRD; no `CLEAN`; conservative default |
| Spark of a false safety claim | High/High | README/ARCHITECTURE say "not a verifier" |

Open questions:

- **O1 — `assay mcp` name?** [Yes; it is an inspection command, not `check`.]
- **O2 — env values?** [Refuse in Stage A; no secrets in the jail.]
- **O3 — exit 0 on a started server?** [Yes, inspection success; the output explicitly says no
  verdict.]
- **O4 — Stage B scope?** [Driver registration + task + TOOL evidence + a conservative assessment;
  its own PRD.]
- **O5 — bundle/Server trace?** [Deferred; the `Skill` trace is not a server trace.]

Challenge: **is a runtime inspector without a verdict useful?** It answers "does it start, what tools
does it expose, what did the jail deny?" — a real pre-install check and the base for Stage B. It is
not a safety claim, and the output must say so.

## Out of scope (Stage A)

Driver/model, verdict/assessment, bundle, ServerTrace, HTTP/SSE/OAuth, registry/install, third-party
servers, env secrets, changes to A1–A8/A10, the floor, `REVIEW` cap or trace schema.

## Self-critique

- 🔴 **No verdict.** Stage A is an inspector; it cannot say a server is safe.
- 🟡 **Env refusal limits coverage.** Many servers need keys; Stage A refuses rather than leak.
- 🟡 **Manifest format.** Claude Desktop shape only; other hosts differ.
- 🟡 **Relative paths.** The run root is not the manifest directory; a script path may fail.
- 🟡 **Stage B is the hard part.** Dynamic tools and a verdict policy need a separate design; do not
  smuggle them into Stage A.

## Decision

- Build Stage A: `Server` record, manifest parser, runtime inspection, `assay mcp`, report, tests,
  docs.
- Defer Stage B (driver + conservative assessment) to its own PRD/spec.
- No verdict, no `CLEAN`, no bundle, no HTTP/auth/registry, no new dependency.
