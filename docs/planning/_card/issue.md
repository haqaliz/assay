# feat mcp-design — MCP verification design spike (A8 boundary)

## Brief

Decide whether MCP server manifests belong in A8 and, if so, what the first honest slice is. MCP is
not a `SKILL.md` variant: it is a long-lived JSON-RPC client/server protocol (stdio or Streamable
HTTP) where a server exposes tools, resources and prompts, and the host runs an MCP client. The
current pipeline has a `Skill` (instructions + declared scope), a one-shot sandbox `run`, and a
driver whose tools are read/write/http/shell; it has no MCP client and no long-lived sandbox
session. The deliverable is a PRD with options, a recommendation, and a proposed first slice if the
capability is approved. No code, no manifest parser, no server run, no verdict.

Source: `docs/technical/CAPABILITY_ROADMAP.md` A8 and `docs/ROADMAP.md` M2.4 list MCP server
manifests; this spike tests that assumption. Protocol grounded in
`https://modelcontextprotocol.io/docs/learn/architecture` (2026-11-05): host/client/server, stdio and
Streamable HTTP transports, JSON-RPC 2.0, tools/resources/prompts, dynamic `tools/list`, `tools/call`.

## Context carried from the pick

- A8 shipped OpenClaw/ClawHub and Cursor rules; MCP is the last item in its list.
- `src/assay/sandbox/` exposes `run(argv, config)` (one command, captured output/denials); there is
  no session/spawn API.
- `src/assay/agent/` drives a model with `Toolbox` tools (`read_file`, `write_file`, `http_get`,
  `run_shell`); no MCP client, no dynamic tool registration.
- `src/assay/capture/` records tool actions; a server's own file/network behavior is not captured
  beyond the jail's denials.
- Constraints: no real secrets; the sandbox is the only execution path; execution decides the
  verdict; a static scan is a pre-filter, never a verdict.
