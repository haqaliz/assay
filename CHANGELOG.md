# Changelog

All notable changes to Assay.

## [Unreleased]

### Added

- **Experimental MCP spike:** a long-lived `SandboxSession` and a stdlib stdio MCP client
  (`initialize`, `tools/list`, `tools/call`), plus a fixture server. MCP tool calls are captured as
  `EventKind.TOOL` evidence. This is **not** an MCP verifier: there is no `Server` record, driver
  integration, bundle or verdict; a TOOL-only trace is `UNVERIFIED/NO_TRIGGER`. The floor, `REVIEW`
  cap and trace schema are unchanged.
- **MCP server inspector (Stage A):** `assay mcp <manifest>` parses a Claude Desktop-style
  `mcpServers` manifest into a `Server` record, starts one stdio server in Seatbelt, runs
  `initialize`/`tools/list`, and prints a `ServerReport` (startup, protocol, tools, denials). It
  refuses env values and HTTP. **This is not a verifier:** no model, driver, assessment, bundle or
  verdict; exit `0` means "started and listed tools", not safe.
- **MCP server report (Stage B):** `assay mcp-report <manifest> --task ...` registers the server's
  tools with the model (only those tools), runs the task, captures each `tools/call` as `TOOL`
  evidence, and reports `UNVERIFIED` (no-trigger, no-declared-scope, agent/budget failure) or
  `FLAGGED` (instruction text in a tool description/result). **No `CLEAN` or `MALICIOUS`:** a
  manifest declares startup, not behavior, and server syscalls are not mediated. Exit `0` means the
  report was produced, not that the server is safe.
- **Public repo surface:** `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, issue templates
  and a pull-request template; README header/quickstart and GitHub topics.
- **Brand and GitHub Pages:** the Assay logo, a real CLI terminal screenshot, a static `site/`
  landing page and `.github/workflows/pages.yml`.
- **Support:** the same crypto donation link used by the sibling `contig` project is now in the
  README and the site footer.

### Fixed

- `assay.__version__` now matches the packaged version (`0.1.0`) instead of the stale `0.0.1`.

### Changed

- The private own-skill audit dry run was reviewed privately on 2026-11-10. It remains unpublished
  and authorizes no public finding; the M2.3 public-audit gate is unchanged.

### Limits

- The spike pins protocol `2026-07-28`, covers stdio only, and captures denials/tool results, not
  full server syscalls.
- The inspector refuses manifest `env` values (no secrets in the jail), supports stdio only, and
  prints no verdict.
- `mcp-report` is not a pass gate: it only sees tool calls/results/denials, not the server's own
  syscalls; it requires an explicit `--task`, gives the model no built-in tools, and produces no
  bundle.

## [0.1.0] - 2026-11-07

First public release: execution-grounded verification for AI agent skills on macOS.

### Added

- **Ingest (A1):** Claude Code `SKILL.md`, OpenClaw/ClawHub `SKILL.md` with `metadata.openclaw`
  requirements, and Cursor project rules (`.mdc`, `globs`/`alwaysApply` as file scope). A frozen
  `Skill` record with format, requirements and tri-state declared scope; malformed input is a named
  refusal.
- **Sandbox (A2):** macOS Seatbelt jail with confined writes, port-scoped network, a scrubbed
  environment, CPU/wall limits and captured denials.
- **Agent driver (A3):** bounded BYOK loop with Anthropic and OpenAI-compatible providers, including
  keyless local Ollama; every tool call runs in the jail; cost/step/action/wall caps.
- **Capture and diff (A4):** canonical, content-addressed traces of file, network, shell and
  instruction events; observed-vs-declared diff; trace schema 2 with sandbox config hashes.
- **Verdict and strictness (A5):** `CLEAN`/`FLAGGED`/`MALICIOUS`/`UNVERIFIED`, findings with
  evidence, a named `UNVERIFIED` cause, and an unlowerable four-class floor. Four held-out-calibrated
  shell patterns (`dd` to a device, `pty.spawn`, `/dev/tcp/`, `socat` shell) were added without
  changing the contract. The instruction list was calibrated on a separate held-out set (five
  patterns added, two narrowed); instruction findings remain capped at `REVIEW`.
- **Signed bundle (A6):** canonical SSH-signed record carrying the exact `SKILL.md`, trace, sandbox
  hashes and assessment; `assay verify` re-derives the verdict and refuses a signed assessment that
  does not follow (`replay`).
- **Corpus and benchmark (A7):** a 20-case development benchmark, an 8-case held-out shell
  calibration set, and a private 8-case real-world control of the maintainer's own skills;
  `assay corpus` reports precision/recall with denominators, false-`MALICIOUS` ids and `UNVERIFIED`
  coverage.
- **Audit gate (M2.3):** `ETHICS.md`, a disclosure/audit protocol and a finding template. No
  third-party audit has been run or published. A private own-skill runner dry run was executed on
  2026-11-06; it is unreviewed and unpublished.
- **Static pre-filter (A10):** `assay triage` ranks a skill's text with `priority`/`signals` only;
  no verdict, findings, trace, model or sandbox.
- **CLI and CI:** `assay check | bundle | verify | corpus | triage`, `assay --version`, and a macOS
  GitHub Actions workflow that runs the offline suite.

### Limits

- The benchmark is small, synthetic-dominated and single-labeled; its numbers are a regression
  signal, not a population estimate.
- The real-world control is eight own benign skills, one local-model run each; it measures coverage
  and false positives, not detection.
- No public audit; the M2.3 gate needs a second reviewer and the disclosure window.
- MCP server verification is a separate capability, deferred; A9 (hosted/registry) is deferred.
- A bundle covers `SKILL.md`/`.mdc` only, not the rest of a skill directory. `UNVERIFIED` is never a
  pass; `CLEAN` means "matched declared scope in this run".

[0.1.0]: https://github.com/haqaliz/assay/releases/tag/v0.1.0
