# feat mcp-server — MCP server evidence and verdict (Stage A/B)

## Brief

The spike proves a stdio server can run in Seatbelt and Assay can initialize, list and call tools. It
does not ingest a server manifest, keep a `Server` record, expose MCP tools to the driver, or produce
a server verdict.

**Stage A (this build):** parse a Claude Desktop-style `mcpServers` manifest into a `Server` record;
refuse a missing command, an unsupported URL, or env values (no secrets in the jail); start the
server in a `SandboxSession`; initialize and list tools; emit a `ServerReport` with startup,
protocol, tools, denials and the session record. Add `assay mcp <manifest>` with no model and no
verdict. This is a runtime inspector, not a verifier.

**Stage B (next):** register MCP tools with the driver, run a task, capture `tools/call`, and assess.
The verdict policy is conservative: most servers remain `UNVERIFIED` because a manifest declares
startup, not behavior; there is no `CLEAN` claim; a captured `HIGH` action from the agent's own tools
can still be `MALICIOUS`; the floor, `REVIEW` cap and trace schema stay unchanged. Stage B needs its
own PRD/spec before code.

Out of scope for Stage A: model/driver, verdict, bundle, HTTP/SSE/OAuth, registry, installing
third-party servers, env secrets.
