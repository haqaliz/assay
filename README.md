# Assay

**Execution-grounded security verifier for AI agent skills.** Runs a skill in a sandbox against a
real agent, captures what it actually did, and checks that against what it claims to do.

[![Status](https://img.shields.io/badge/status-A1--A4%20engine%20·%20no%20verdicts%20yet-orange)](docs/ROADMAP.md)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)

[Vision](VISION.md) · [Roadmap](docs/ROADMAP.md) · [Architecture](docs/technical/ARCHITECTURE.md) · [Capabilities](docs/technical/CAPABILITY_ROADMAP.md)

---

## Status

**A1–A4 exist; the verdict does not.** What is built and tested, all offline:

- **Ingest** (`src/assay/ingest/`) — parses a Claude Code `SKILL.md` into a frozen `Skill` record
  with a tri-state declared scope (undeclared vs declared none) and a named refusal for malformed
  input.
- **Sandbox** (`src/assay/sandbox/`) — runs a command under a macOS Seatbelt jail: writes confined
  to a run root, network deny-by-default with a port-scoped allowlist, a scrubbed environment,
  CPU/wall limits, and a capture channel the child cannot rewrite.
- **Agent driver** (`src/assay/agent/`) — a bounded BYOK loop: the model runs outside the jail, every
  tool call runs inside it, with cost, step, action and wall caps and a named stop cause.
- **Capture and diff** (`src/assay/capture/`) — turns a run into a canonical, content-addressed
  trace of file, network, shell and instruction events and diffs it against the declared scope.

There is no verdict, strictness level, CLI or bundle yet, and the first real keyed run has not
happened. Read `CLAUDE.md` before writing any code here; do not describe capability that is not in
`git log`.

## What Assay is

Point Assay at a skill — a Claude Code `SKILL.md` first, with other formats (OpenClaw/ClawHub,
Cursor rules, MCP servers) to follow. It runs the skill in an isolated sandbox against a real
agent, captures every file access, network call, shell command, and injected instruction it
produced, and diffs that against what the skill declares about itself. The verdict is backed by
a replayable record of the run.

## What Assay is not

- Not a static pattern scanner. Those exist (NVIDIA's SkillSpector) and are a useful cheap
  pre-filter, not a verdict.
- Not an antivirus signature match. Assay observes novel behavior, not known hashes.
- Not a claim that a `CLEAN` skill is safe forever — only that this run's observed behavior
  matched its declared scope.

## The verdict

| Verdict | Meaning |
|---|---|
| `CLEAN` | Observed behavior matched declared scope |
| `FLAGGED` | A finding fired, below the user's block threshold |
| `MALICIOUS` | A captured, reproduced bad behavior — never inferred from text alone |
| `UNVERIFIED` | Could not decide (sandbox failure, cost cap, conditional path never triggered) |

A static scan or model may flag a candidate; the sandboxed, observed run assigns the verdict.

## Docs

- [`VISION.md`](VISION.md) — the thesis, the moat, non-goals.
- [`CLAUDE.md`](CLAUDE.md) — guardrails and the verdict contract.
- [`docs/ROADMAP.md`](docs/ROADMAP.md) — phased plan and risk register.
- [`docs/technical/CAPABILITY_ROADMAP.md`](docs/technical/CAPABILITY_ROADMAP.md) — A1..A10 capabilities in build order.
- [`docs/technical/ARCHITECTURE.md`](docs/technical/ARCHITECTURE.md) — the design.

## Lineage

Assay is one of three siblings scaffolded together on 2026-10-22 (with [Tenon](../tenon) and
[Pry](../pry)), out of a market-demand research pass, sharing house DNA with
[Belay](../belay), [Plumb](../plumb), and [Whetstone](../whetstone). Standalone by design — no
code dependency on sibling projects yet.
