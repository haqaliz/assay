# PRD — `mcp-design` (MCP verification design spike)

Status: design spike, 2026-11-05. No code. Decision: **do not ship an MCP manifest parser as an A8
adapter; MCP verification is a separate capability, deferred.**
Pipeline position: A8 boundary / M2.4. A8's file-based adapters (OpenClaw/ClawHub, Cursor rules) are
shipped; MCP is the remaining name on the A8 list.

## Problem statement

The A8 row lists "MCP server manifests" next to `SKILL.md` and Cursor rules. That framing is wrong.
A `SKILL.md` or a `.mdc` is a file of instructions with a declared scope; Assay can load it, run the
model, and diff observed behavior. An MCP server is a **program** that speaks a long-lived JSON-RPC
protocol and exposes tools, resources and prompts. A manifest only says how to start it. There is no
instruction body, no declared behavior, no one-shot command, and no MCP client or long-lived sandbox
session in the engine.

Shipping a manifest parser as "MCP support" would be a static scan wearing an adapter's clothes. It
could inventory a config, not verify a server. That violates the project's first constraint:
execution decides the verdict.

For whom: a user who wants to check an MCP server before installing it; a registry/CI gate; the
maintainer deciding whether MCP belongs in the next three months.

## What MCP actually is

Grounded in `https://modelcontextprotocol.io/docs/learn/architecture` (2026-11-05):

- A **host** (an AI application) creates one **client** per **server**.
- A local server uses **stdio** (JSON-RPC over stdin/stdout); a remote server uses **Streamable
  HTTP** (POST + optional SSE, standard auth).
- Servers expose **tools** (executable functions), **resources** (data) and **prompts** (templates).
  Tool lists are dynamic (`tools/list`), and calls are `tools/call`.
- The protocol is JSON-RPC 2.0, long-lived, and versioned; the current docs describe protocol
  `2026-07-28` with per-request metadata and `server/discover`.
- A server is arbitrary code with its own filesystem, network and environment needs.

## Why it is not an A8 file adapter

| A8 file adapter | MCP server |
|---|---|
| One file (`SKILL.md` / `.mdc`) | A manifest plus a program and its runtime |
| Instructions + declared scope | Tools discovered at runtime; no behavior declaration |
| One-shot sandbox `run(argv, config)` | Long-lived process with stdin/stdout or HTTP |
| Driver tools: read/write/http/shell | Driver needs an MCP client and dynamic tool registration |
| Capture records tool actions | Server's own file/network behavior is not captured beyond denials |
| `CLEAN`/`FLAGGED` from scope diff | The manifest declares startup, not behavior; most runs would be `UNVERIFIED` |

## Options

**A. Manifest-only ingest + pre-run requirements gate.** Parse `mcpServers` (`command`, `args`,
`env`, `url`), record them, refuse if the command/env is unavailable. No server run. This is
inventory, not verification: no verdict above `UNVERIFIED` is possible, and calling it "support"
would be the static trap. Only acceptable as a clearly labeled manifest report, not a verdict.

**B. Sandboxed MCP session + client (the real capability).** Spawn the server inside the jail,
speak MCP over stdio (Streamable HTTP later), discover tools, expose them to the model, run a task,
capture `tools/call` and the server's denials. Requires:

1. a `SandboxSession` API (spawn a long-lived process, JSON-RPC framing, timeouts, teardown) — the
   current `Sandbox.run` is one-shot;
2. an MCP client (discover/initialize, `tools/list`, `tools/call`) with a pinned protocol version;
3. a `Server` record (manifest, command/args/env/url) and a task derived from the tool list;
4. driver integration: register MCP tools alongside the existing four; capture the calls;
5. a verdict policy: the manifest is not a behavior declaration, so `UNVERIFIED` unless a captured
   dangerous action is `HIGH` (MALICIOUS) or a file/network/shell divergence is `FLAGGED`; tool
   descriptions/resources can carry prompt injection and must be treated as untrusted input.

This is a multi-slice capability, not an adapter. It may be the right product, but it is not a
one-week A8 tail.

**C. Static manifest scan.** Command/args/env/url patterns, known-bad packages. Not
execution-grounded; only a pre-filter. Reject as the capability.

**D. Defer.** Ship the file-based adapters, keep MCP out of A8, and revisit with a dedicated
capability when the session/client design is funded.

## Recommendation

**D now, with B as the proposed capability if pursued.** M2.4 is complete for the formats Assay can
honestly verify (`SKILL.md` and `.mdc`). MCP should be reclassified out of A8 as a separate
capability (proposed **A11 — MCP server verification**, not scheduled). Do not ship A as
verification; if users need inventory, a separate `--dry-run` manifest report can be added later
with a clear `UNVERIFIED/UNSUPPORTED` label.

If B is approved, the first slice is a **spike, not a verdict**: `SandboxSession` + a stdio MCP
client against a trivial local server (initialize, `tools/list`, one `tools/call`), with timeouts and
teardown. Only after that works should the `Server` record, driver integration and capture be
designed.

## Proposed first slice (if B is approved)

1. `SandboxSession` behind the `Sandbox` seam: spawn, framed stdin/stdout, wall/step limits, kill
   process group, capture stdout/stderr/denials. No unconfined fallback.
2. A minimal MCP stdio client with a pinned protocol version: `initialize`/`discover`, `tools/list`,
   `tools/call`, timeouts, max message size. No sampling/elicitation.
3. A `Server` record and manifest parser (`mcpServers`: name, command, args, env, url) — a separate
   type from `Skill`, not a fake `Skill`.
4. A fixture server (a tiny Python stdio server) and a test that lists one tool and calls it.
5. Then, separately: expose the tool to the driver, derive a task, capture the call, and decide the
   verdict policy.

## Risks and open questions

| Risk | L/I | Mitigation |
|---|---|---|
| Shipping a manifest parser as "verification" | High/High | Reject option A; no verdict above `UNVERIFIED` |
| A server is arbitrary code | High/Critical | Spawn only in the jail; no unconfined path; timeouts/teardown |
| Secrets in `env` / remote auth | High/High | Never inject real secrets; redact; BYOK only; allowlist network |
| Long-lived process capture | High/Med | `SandboxSession` design first; capture denials and tool calls, not full syscalls |
| Runtime bins outside the jail PATH | Med/Med | The server's runtime must be in the jail; otherwise a named refusal |
| Protocol churn (2026-07-28) | Med/Med | Pin a version; one transport first (stdio) |
| Tool descriptions/resources are prompt injection | High/High | Treat as untrusted; the instruction cap applies; never a verdict from text |
| No behavior declaration | High/Med | Most runs `UNVERIFIED`; say so; do not fake `CLEAN` |
| MCP is a different product surface | Med/High | Reclassify; do not stretch A8 |

Open questions:

- **O1 — is MCP in scope for the next three months?** [No; file-based formats + the audit first.]
- **O2 — stdio or HTTP first?** [Stdio; local servers are the common install path.]
- **O3 — what is "declared" for a server?** [The manifest's startup requirements, not behavior; the
  verdict is mostly `UNVERIFIED`.]
- **O4 — a manifest inventory tool?** [Separate, clearly `UNVERIFIED`, not a verdict.]
- **O5 — reclassify as A11?** [Yes; A8 is file-based adapters.]

## Out of scope

- Any MCP code, manifest parser, server spawn, client, or verdict in this unit.
- Remote OAuth, all transports, the full MCP spec, registry integration.
- A manifest-only "support" claim.
- Changes to A5, trace, bundle, corpus.

## Areas to strengthen before sharing (self-critique)

- 🔴 **This is a "no" to a listed A8 item.** The docs and the user may expect MCP; the honest answer
  is that it is a different capability. Say it plainly and keep the door open with a concrete
  proposed slice.
- 🟡 **The demand is unproven.** No user has asked for MCP specifically; the registry/CI case is
  plausible but not measured. A manifest inventory would be cheap but not the moat.
- 🟡 **The verdict model is weak for servers.** Without a behavior declaration, most runs are
  `UNVERIFIED`; a captured dangerous action can still be `MALICIOUS`, but the "declared vs observed"
  story is thinner than for skills.
- 🟡 **The session API is the real work.** It is also useful beyond MCP (long-running tools), but it
  is a sandbox/A3 change, not an adapter.
- Question before greenlighting: **would a manifest inventory alone be useful, even without a
  verdict?** [Maybe, as a separate clearly-labeled report; not as A8 and not as verification.]

## Decision

- A8 = file-based formats: Claude Code `SKILL.md`, OpenClaw/ClawHub `SKILL.md`, Cursor `.mdc`.
  **MCP is not an A8 adapter.**
- MCP verification is a separate capability (proposed A11), **not scheduled**; if approved, start
  with a `SandboxSession` + stdio client spike, not a manifest parser.
- M2.4 is complete for the file-based adapters; the roadmap marks MCP as reclassified/deferred.
