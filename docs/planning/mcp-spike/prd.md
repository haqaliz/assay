# PRD — `mcp-spike` (SandboxSession + stdio MCP client)

Status: proposed spike, 2026-11-07. Awaiting approval; no code yet.
Parent: `docs/planning/mcp-design/prd.md` — MCP is a separate capability, and its first slice is a
spike, not a verdict.

## Problem

Assay can verify a file-based skill because it can parse the file, run a model in a jail, and diff
observed behavior. An MCP server is a long-lived JSON-RPC program; it has no instruction body and no
declared behavior. A manifest parser would only inventory startup, which is the static-scan trap the
project forbids.

The engine has neither a long-lived sandbox session nor an MCP client. Before designing a `Server`
record, driver integration, or a verdict policy, prove the foundation: can a server run inside the
jail and can Assay speak enough MCP to list and call a tool without weakening the sandbox or the
verdict contract?

## Scope tree

```
MCP spike
├─ SandboxSession        spawn, pipes, stderr drain, request deadline, killpg, teardown
├─ MCP stdio client      initialize, notifications/initialized, tools/list, tools/call
├─ Fixture server        echo, read inside the run root, attempt an outside read
├─ Evidence              each call -> EventKind.TOOL; no event/schema/verdict change
└─ Tests                 offline framing + real macOS session/confinement
   ✗ manifest parser
   ✗ Server record / bundle
   ✗ driver integration / dynamic tool registration
   ✗ verdict policy for MCP
   ✗ HTTP, SSE, OAuth, registry
   ✗ CLI command
```

## Goals and success metrics

| Goal | Metric |
|---|---|
| A session survives the jail | A stdlib stdio server spawns inside Seatbelt and answers more than one request |
| MCP handshake works | `initialize` returns, `notifications/initialized` is accepted, `tools/list` returns the fixture tools |
| A tool call executes | `tools/call` for `echo` and `read_inside` returns the expected text |
| The jail holds | `read_outside` cannot read `/private/etc/hosts`; the denial is captured, not silently ignored |
| No hang or orphan | A request deadline returns a named error; `close()` kills the process group and leaves no child |
| Evidence, not a verdict | Each call becomes `EventKind.TOOL`; a TOOL-only trace is `UNVERIFIED/NO_TRIGGER`; no new `EventKind`, `Trace.schema`, `FindingClass`, or floor change |
| No new dependency | Client, session and fixture use only the Python standard library |

## Users and scenarios

1. **Maintainer** — proves the session/client foundation before committing to the larger MCP
   capability.
2. **Future user** — wants to check an MCP server before installing it; this spike does not yet give
   them a verdict.
3. **Future slice** — the session API is the reusable piece for long-running tools beyond MCP.

## Requirements

### Must have

1. **`SandboxSession`** in `src/assay/sandbox/session.py`:
   - spawn `sandbox-exec` with `stdin=PIPE`, `stdout=PIPE`, `stderr=PIPE`, `cwd=run_root`,
     `start_new_session=True`, and `preexec_fn=_limit_setter(limits)`;
   - expose line-oriented `write` / `readline(deadline)` with a bounded line size;
   - drain stderr concurrently into a bounded buffer; never merge it with stdout;
   - detect a startup failure (`sandbox-exec:` / exit 65/71) and raise `SandboxFailed`;
   - `close()` closes stdin, kills the process group, waits briefly, joins the drain, and removes
     the run root unless `keep=True`;
   - no unconfined fallback.
2. **MCP stdio client** in `src/assay/mcp/client.py`:
   - newline-delimited JSON-RPC 2.0, id correlation, one JSON object per line;
   - `initialize` with a pinned `protocolVersion` and `clientInfo`, then
     `notifications/initialized`;
   - `tools/list` (first page only) and `tools/call`;
   - per-request deadline, maximum line size, JSON-RPC error and `isError` handling;
   - named errors (`MCPError`, `MCPTimeout`, `MCPProtocolError`); no silent skip of non-JSON lines.
3. **Fixture server** `tests/fixtures/mcp_server.py`:
   - stdlib only, `python3 -u`, stdout is protocol-only, diagnostics to stderr;
   - tools: `echo`, `read_inside` (a file in the run root), `read_outside` (`/private/etc/hosts`);
   - the outside read emits an `assay-denial:` line and returns an error result.
4. **Evidence mapping**:
   - one `Event(kind=EventKind.TOOL, target=tool, outcome=ok/denied/failed,
     content_sha256=..., content_bytes=..., excerpt=..., input_sha256=..., request="tools/call")`
     per call;
   - no new `EventKind`; no `Trace`/bundle/`Server` identity in this slice; the event list is the
     spike output.
5. **Tests**:
   - offline: fake session/pipe covers framing, id correlation, timeout, malformed line, JSON-RPC
     error, `isError`; no model/network;
   - real macOS: session + client against the fixture, inside read succeeds, outside read is denied,
     timeout/teardown leaves no orphan;
   - verdict: a TOOL-only trace is `UNVERIFIED/NO_TRIGGER`; TOOL is not behavior; no finding/floor
     change.
6. **Docs**: this PRD, a `core` spec and plan; a short note in `docs/technical/ARCHITECTURE.md` that
   the spike is evidence-only; no README "MCP supported" claim.
7. **No new dependency; verdict contract, floor and cap unchanged.**

### Should have

8. A `SessionRecord` (exit code, signal, stderr, denials, config hash) for diagnostics, without
   pretending it is a `RunRecord`.
9. A cleanly separable `src/assay/mcp/` module so the spike can be removed if it does not prove out.

### Nice to have (deferred)

- `Server` record and manifest parser; driver integration/dynamic tools; MCP verdict policy; HTTP
  transport; auth; registry/CLI; trace persistence/bundle; pagination; sampling/elicitation.

## Technical considerations

- **Why module-only.** A CLI command would imply a user-facing capability before the `Server` record
  and verdict policy exist. The tests are the proof.
- **Why `EventKind.TOOL`.** It already exists, is ignored by `diff`/`assess`, and a TOOL-only trace is
  `UNVERIFIED/NO_TRIGGER`. That is honest evidence without a verdict. Adding an `mcp` kind would force
  a `Trace.schema` change and a new policy; out of scope.
- **Why no `Trace`.** `Trace` is `Skill`-shaped; a server is not a skill. Faking a `Skill` would
  contaminate the bundle/replay path. The spike returns events; the `Server` identity is the next
  slice.
- **Why a session, not repeated one-shots.** MCP is long-lived; `SeatbeltSandbox.run` blocks on exit
  and deletes the root. The session reuses the profile/limits/kill helpers but owns `Popen`.
- **Pipes.** Python block-buffers stdout on a pipe; the fixture uses `-u`. Stderr must be drained or
  a chatty server deadlocks.
- **Limits.** `RLIMIT_CPU` is cumulative; the wall budget is per request, not `proc.wait`. A timed-out
  request tears the session down rather than leaving it ambiguous.

## Risks and open questions

| Risk | L/I | Mitigation |
|---|---|---|
| Protocol churn | Med/Med | Pin the fixture's version; no `server/discover`; label provisional |
| stderr deadlock | Med/High | Concurrent drain into a bounded buffer |
| Orphan/daemonizing server | Med/High | `start_new_session` + `killpg`; teardown test |
| Pipe buffering/framing | Med/Med | `-u`, one JSON line, max line cap, reject non-JSON |
| Denial evidence is partial | High/Med | Capture denials/tool results, not full syscalls; say so |
| Accidental verdict claim | High/High | TOOL-only; no `Skill`/bundle; docs say evidence-only |
| Session API leaks into A2 | Med/Med | Separate module; no `Sandbox` protocol change in the spike |

Open questions:

- **O1 — persist a trace?** [No; events in memory. `Server` identity/trace is the next slice.]
- **O2 — CLI?** [No; module + tests only.]
- **O3 — protocol version?** [Pin the fixture's version, documented as provisional; no discovery.]
- **O4 — expose the session on `Sandbox`?** [No; standalone class first, protocol later.]
- **O5 — install third-party servers?** [No; fixture only.]

Challenge: **is a session/client that produces no verdict useful?** Yes, if it proves the jail can
hold a long-lived program and the client can speak the protocol; without it, any MCP "support" would
be a manifest scan. It is a foundation, not a release claim.

## Out of scope

Manifest parser; `Server` record; `Skill`/`Trace`/bundle integration; driver/dynamic tools; MCP
verdict policy; HTTP/SSE/OAuth; registry/CLI; third-party servers; changes to A1–A8/A10, the trace
schema, the bundle, the corpus, the floor or the `REVIEW` cap.

## Areas to strengthen before sharing (self-critique)

- 🔴 **No verdict.** The spike cannot tell a user whether a server is safe; say it plainly.
- 🟡 **Pinned protocol.** The fixture and client can agree while the real ecosystem differs; a
  protocol-version check is part of the proof, not a claim of broad support.
- 🟡 **Partial capture.** The server's own file/network behavior is visible only through denials and
  tool results; no syscall tracing.
- 🟡 **Session API risk.** A long-lived process under `RLIMIT_CPU` is cumulative; the next slice must
  decide whether the CPU budget is per session or per request.
- Question before greenlighting: **should the spike return a `SessionRecord`/events only, or also a
  minimal `Server` identity?** [Events only; a fake `Skill`/`Server` would contaminate the bundle and
  verdict path.]
