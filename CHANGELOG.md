# Changelog

All notable changes to Assay. The project is pre-release; this file starts at `Unreleased` and does
not yet name a version or a release date.

## [Unreleased]

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
  changing the contract.
- **Signed bundle (A6):** canonical SSH-signed record carrying the exact `SKILL.md`, trace, sandbox
  hashes and assessment; `assay verify` re-derives the verdict and refuses a signed assessment that
  does not follow (`replay`).
- **Corpus and benchmark (A7):** a 20-case development benchmark, an 8-case held-out shell
  calibration set, and a private 8-case real-world control of the maintainer's own skills;
  `assay corpus` reports precision/recall with denominators, false-`MALICIOUS` ids and `UNVERIFIED`
  coverage.
- **Audit gate (M2.3):** `ETHICS.md`, a disclosure/audit protocol and a finding template. No
  third-party audit has been run or published.
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
