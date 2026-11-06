# feat mcp-spike — sandboxed MCP stdio session

## Brief

Prove Assay can verify an AI agent skill that depends on an MCP server. Today A1–A8/A10 handle
file-based skills and a fixed tool surface; MCP is a separate runtime capability, not an adapter.

The spike must:

1. add a `SandboxSession` that keeps a process alive inside the macOS Seatbelt jail (the current
   `SeatbeltSandbox.run` is one-shot);
2. add a minimal MCP JSON-RPC stdio client: `initialize`, `tools/list`, `tools/call`, errors and
   timeouts;
3. run a local test MCP server end to end, capture its tool calls in the trace, and verify the
   sandbox boundary (a read inside the run root succeeds; an outside access is denied);
4. keep the verdict contract unchanged: MCP calls are evidence, not a static-manifest verdict.

Out of scope: remote/HTTP MCP transports, auth, registry discovery, installing third-party MCP
servers, exposing MCP tools to the LLM driver, changing the verdict classes/floor, hosted A9.

No new dependency: the client and test server use the Python standard library. The spike is
experimental and may be merged behind a module boundary or left unshipped if it does not prove out.
