# Assay

**Execution-grounded security verifier for AI agent skills.** Runs a skill in a sandbox against a
real agent, captures what it actually did, and checks that against what it claims to do.

[![Status](https://img.shields.io/badge/status-A1--A7%20+%20A8%2FOpenClaw%2BCursor%20+%20A10%20·%20offline-orange)](docs/ROADMAP.md)
[![CI](https://github.com/haqaliz/assay/actions/workflows/ci.yml/badge.svg)](https://github.com/haqaliz/assay/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/assayhq.svg)](https://pypi.org/project/assayhq/)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)

[Vision](VISION.md) · [Roadmap](docs/ROADMAP.md) · [Architecture](docs/technical/ARCHITECTURE.md) · [Capabilities](docs/technical/CAPABILITY_ROADMAP.md)

---

## Install

Sandboxed checks require macOS. Install the CLI with `uv` or `pip`:

```sh
uv tool install assayhq
# or
pip install assayhq
```

From a checkout, `uv sync --dev` then `uv run assay ...` works too.

## Status

**A1–A7 exist, plus two A8 adapters (OpenClaw/ClawHub and Cursor rules) and the A10 static
pre-filter; the engine has a verdict, a portable record and a measured benchmark.** What is built and
tested, all offline (the bundle tests run a local `ssh-keygen`; the benchmark makes no model or
network call):

- **Ingest** (`src/assay/ingest/`) — parses a Claude Code `SKILL.md`, an OpenClaw/ClawHub
  `SKILL.md` (format plus `metadata.openclaw` requirements), and a Cursor project rule (`.mdc`,
  `globs`/`alwaysApply` as file scope) into a frozen `Skill` record with a tri-state declared scope
  (undeclared vs declared none) and a named refusal for malformed input. A declared
  `env`/`config`/`os` requirement the jail cannot satisfy, or a missing required binary, is refused
  before a run with `UNVERIFIED/REQUIREMENTS_UNMET`.
- **Sandbox** (`src/assay/sandbox/`) — runs a command under a macOS Seatbelt jail: writes confined
  to a run root, network deny-by-default with a port-scoped allowlist, a scrubbed environment,
  CPU/wall limits, and a capture channel the child cannot rewrite.
- **Agent driver** (`src/assay/agent/`) — a bounded BYOK loop: the model runs outside the jail, every
  tool call runs inside it, with cost, step, action and wall caps and a named stop cause.
- **Capture and diff** (`src/assay/capture/`) — turns a run into a canonical, content-addressed
  trace of file, network, shell and instruction events and diffs it against the declared scope.
- **Verdict and strictness** (`src/assay/verdict/`) — turns that diff into one `Assessment` with a
  `CLEAN/FLAGGED/MALICIOUS/UNVERIFIED` verdict, findings with evidence, a named cause when
  undecidable, and a `blocked` flag. The four-class severity floor cannot be lowered.
- **CLI** (`src/assay/cli/`) — `assay check <skill>` composes A1–A5, saves the trace, prints a
  human or canonical JSON report, and exits `0` only on `CLEAN`.
- **Signed bundle** (`src/assay/bundle/`) — turns a saved trace and its `SKILL.md` into one
  canonical record with the exact skill source, the observed trace, the sandbox config hashes and
  the verdict, signed with `ssh-keygen`. `assay verify` checks the hashes and the signature offline,
  re-parses the embedded source and re-runs the shipped verdict layer; a signed assessment that does
  not follow from the record is refused. The bundle proves the record is intact, who attested it,
  and that the verdict follows from the recorded inputs. It does not prove the run happened or that
  the skill is safe.
- **Labeled corpus and benchmark** (`src/assay/corpus/`, `corpus/`) — 20 labeled cases (18 synthetic,
  2 local-model) scored offline by `assay corpus`, with precision and recall, explicit denominators,
  the ids of any false `MALICIOUS` on clean cases, and `UNVERIFIED` coverage by cause. Single labeler
  and synthetic-dominated: a regression measurement, not a population estimate. A separate 8-case
  real-world control (`corpus/real/`) holds one local-model run of each of the maintainer's own
  Plumb skills, all labeled clean; it is a private false-positive and coverage control, not a
  benchmark.
- **Static pre-filter** (`src/assay/triage/`, `assay triage`) — ranks a skill for a run from its
  text; it emits `priority` and `signals` only, with no verdict, findings, trace or run. It is a
  queue heuristic, not a detector, and the sandboxed run remains the verdict.
- **Audit gate** ([`ETHICS.md`](ETHICS.md), [`docs/audit/`](docs/audit/)) — the rules and protocol
  for third-party audits: evidence, three private runs, two-person review, a disclosure window,
  publication limits and corrections. **No third-party audit has been run or published.** A private
  own-skill runner dry run was executed on 2026-11-06 and privately reviewed on 2026-11-10; it
  remains unpublished. The maintainer is the only reviewer today; a public finding waits for a
  second reviewer and the disclosure steps.

The pattern lists are now measured on that corpus; run `assay corpus corpus/` for the current
numbers and read `corpus/README.md` for the limits. The first real Anthropic-keyed run has not
happened (the Phase 0 gate used a local model). Read `CLAUDE.md` before writing any code here; do not
describe capability that is not in `git log`.

## Usage

```sh
ANTHROPIC_API_KEY=... uv run assay check path/to/SKILL.md \
  --model claude-sonnet-4-5 --input-price 3 --output-price 15 --max-cost 0.50
```

A local model needs no key at all. With Ollama running:

```sh
uv run assay check path/to/SKILL.md \
  --provider openai-compatible --base-url http://127.0.0.1:11434/v1 \
  --model qwen3-coder:30b --input-price 0 --output-price 0 --max-cost 0.01
```

`<skill>` may be the `SKILL.md` file or its directory. `--model`, `--input-price`,
`--output-price` and `--max-cost` are required, with env fallbacks `ASSAY_MODEL`,
`ASSAY_INPUT_PRICE`, `ASSAY_OUTPUT_PRICE` and `ASSAY_MAX_COST`; the OpenAI-compatible provider also
reads `ASSAY_API_KEY`, but only for a non-local base URL (local URLs need no key, and a non-local URL
must be https). Prices are USD per million tokens. Traces are written to
`./.assay/traces/<sha256>.json` unless `--out` says otherwise, and `--json` prints one canonical
line for CI. Exit `0` only on `CLEAN`; `1` on `FLAGGED`, `MALICIOUS` or `UNVERIFIED` (including a
sandbox that cannot start, or a declared requirement the jail cannot satisfy); `2` on a usage or
config error. The suite injects a scripted model and fake sandbox; a real Anthropic-keyed run is
still the maintainer's.

Claude Code, OpenClaw/ClawHub `SKILL.md` files, and Cursor project rules (`.mdc`) are accepted; the
report's `format` and `requirements` fields say which and what it declares. An OpenClaw skill whose
requirements cannot be met in the jail (`requires.env`, `requires.config`, a mismatched `os`, or a
required binary absent from the jail PATH) is refused before any run with
`UNVERIFIED/REQUIREMENTS_UNMET` and the exact missing item. A satisfiable skill runs normally. Most
OpenClaw skills declare no file/network/tool scope, so the run stays
`UNVERIFIED/NO_DECLARED_SCOPE` unless `metadata.assay` adds one.

A Cursor rule's `globs` (or `alwaysApply: true`) becomes its file scope; the format declares no
tools or network, so a run with no findings stays `UNVERIFIED/NO_DECLARED_SCOPE`, and a write outside
the globs is `FLAGGED`. Pass the `.mdc` file itself, not its directory. `AGENTS.md`, `.cursorrules`,
and Cursor user/team rules are not project-rule files and are out of scope.

### Attesting a run

A bundle binds one saved trace to the `SKILL.md` that produced it. Use a dedicated, unencrypted
attestation key:

```sh
ssh-keygen -t ed25519 -N '' -C assay-attest -f ~/.ssh/assay-attest
uv run assay bundle .assay/traces/<sha256>.json \
  --skill path/to/SKILL.md --key ~/.ssh/assay-attest
uv run assay verify .assay/traces/<sha256>.bundle.json \
  --public-key ~/.ssh/assay-attest.pub
```

`bundle` writes `<trace-stem>.bundle.json` next to the trace unless `--out` says otherwise, and
exits `0` only when it wrote the file. `verify` exits `0` only when the record is canonical, every
hash agrees, and the signature verifies against the public key you supply; `1` on any failure, `2`
on a usage error. Both accept `--json`. The bundle embeds the trace, so a verifier needs only the
bundle and the public key — never the private key, the model, or the sandbox. A bundle embeds the
trace's event excerpts, so read it before publishing. Pass the same `--strictness` you checked
with (the default is `standard`); the bundle records the level it used. `verify` checks the
signature and then replays the verdict: it re-parses the embedded `SKILL.md`, re-runs the shipped
verdict layer at the recorded strictness, and refuses unless the result matches (`replay: verified`).
A valid signature over a false verdict therefore fails with `replay-mismatch`. Replay proves the
verdict follows from the recorded inputs, not that the run was captured honestly or that the skill
is safe; the skill hash covers `SKILL.md` only, not the rest of the skill directory. `CLEAN` still
means "matched declared scope in this run".

### Measuring the verdict

The repo ships a labeled corpus and an offline benchmark:

```sh
uv run assay corpus corpus/
uv run assay corpus corpus/ --json
```

It verifies every case's skill and trace hash, re-runs the verdict layer, and prints precision and
recall with explicit denominators, `UNVERIFIED` counts by cause, and the ids of any false
`MALICIOUS` on clean cases. Exit `0` means the report was computed, not that the numbers passed a
threshold. The corpus is small, single-labeled and synthetic-dominated; `corpus/README.md` states
the limits, and the numbers are a regression signal, not a population estimate.

### Triaging a collection

`assay triage <skill>` ranks a skill from its text before you spend a run:

```sh
uv run assay triage path/to/SKILL.md
uv run assay triage path/to/SKILL.md --json
```

It prints `priority` (`low`/`medium`/`high`) and the `signals` that produced it (credentials,
network, shell, install, persistence, prompt injection, destructive, privilege, filesystem). It is a
pre-filter: no verdict, no findings, no trace, no model and no sandbox. A high priority is not
`MALICIOUS`, and a low priority is not safe; run `assay check` for an observed verdict.

### Inspecting an MCP server

`assay mcp <manifest>` starts one stdio server from a Claude Desktop-style `mcpServers` manifest,
initializes it, and lists its tools:

```sh
uv run assay mcp path/to/mcp.json
uv run assay mcp path/to/mcp.json --name my-server --json
```

It prints startup, protocol, tool names and jail denials, and **no verdict**. It refuses manifest
`env` values (no secrets in the jail) and HTTP transport. Exit `0` means the server started and
listed tools, not that it is safe.

### Running an MCP task

`assay mcp-report <manifest> --task "..."` gives the model only the server's tools, runs the task,
and captures each `tools/call` as evidence:

```sh
uv run assay mcp-report path/to/mcp.json \
  --task "Read the project README and summarize it" \
  --model qwen3-coder:30b --provider openai-compatible --base-url http://127.0.0.1:11434/v1 \
  --input-price 0 --output-price 0 --max-cost 0.01 --json
```

It reports `UNVERIFIED` (no trigger, no declared scope, or a failed run) or `FLAGGED` when tool
descriptions/results contain instruction-like text. There is **no `CLEAN` or `MALICIOUS`**: a
manifest declares startup, not behavior, and the server's own syscalls are not mediated. Exit `0`
means the report was produced, not that the server is safe. It has no bundle.

## What Assay is

Point Assay at a skill — a Claude Code or OpenClaw/ClawHub `SKILL.md`, or a Cursor project rule
today. MCP server verification is a separate, deferred capability: a server is a long-lived program,
not a file. It runs the skill in an isolated sandbox against a real
agent, captures every file access, network call, shell command, and injected instruction it
produced, and diffs that against what the skill declares about itself. The verdict is backed by
a captured record of the run, which can be signed into a bundle a third party verifies offline.

## What Assay is not

- Not a static pattern scanner as a verdict. Those exist (NVIDIA's SkillSpector) and are a cheap
  pre-filter; `assay triage` is our queue heuristic, and it never decides. Only the sandboxed run
  assigns a verdict.
- Not an antivirus signature match. Assay observes novel behavior, not known hashes.
- Not an MCP server verifier yet. `assay mcp` inspects startup/tools; `assay mcp-report` runs a
  task with only the server's tools and reports `UNVERIFIED` or `FLAGGED`. There is no `CLEAN` or
  `MALICIOUS`: a manifest declares startup, not behavior, and the server's own syscalls are not
  mediated. Exit `0` means the report was produced, not safe; there is no bundle. MCP verification
  remains a separate, deferred capability (see
  [`docs/planning/mcp-design/prd.md`](docs/planning/mcp-design/prd.md)).
- Not a claim that a `CLEAN` skill is safe forever — only that this run's observed behavior
  matched its declared scope.

## The verdict

| Verdict | Meaning |
|---|---|
| `CLEAN` | No findings, all three dimensions declared, and at least one captured behavior event |
| `FLAGGED` | At least one finding, none of them `HIGH` |
| `MALICIOUS` | At least one `HIGH` finding from a captured `OK`/`DENIED` action — never inferred from text alone |
| `UNVERIFIED` | Could not decide; carries `NO_TRIGGER`, `NO_DECLARED_SCOPE`, `AGENT_FAILED`, `BUDGET_LIMIT` or `COST_CAPPED` |

Strictness (`baseline`/`standard`/`strict`) decides only whether a run is `blocked`; it never
changes the verdict. The severity floor for the four finding classes is fixed and cannot be
lowered. An instruction-pattern match is a candidate capped at `REVIEW`: it can make a run
`FLAGGED`, never `MALICIOUS`. The shell and instruction pattern lists are deliberately short. The A7
corpus measures them on 20 labeled cases; the shell list was calibrated on a separate 8-case
held-out set, adding four `HIGH` patterns (`dd` to a device, `pty.spawn`, `/dev/tcp/`, `socat ...
EXEC:/bin/sh`) and taking strict malicious recall from 0/4 to 4/4 with 0 false `MALICIOUS` on four
clean guards. The instruction list was calibrated on its own 8-case held-out set: five patterns were
added (`ignore the above`, `disregard previous`, `forget your instructions`, `keep this between us`,
`do not reveal this`) and two narrowed (`override your`, `system prompt`), taking detection from 0/4
to 4/4 and clean review from 2/4 to 0/4 with 0 false `MALICIOUS`. Both sets are small and synthetic;
those numbers are a regression/calibration signal, not a population estimate. Instruction findings
remain capped at `REVIEW` — `FLAGGED` is a review, never an accusation — so strict malicious recall
stays 0/4 by design.

A static scan or model may flag a candidate; the sandboxed, observed run assigns the verdict.

## Development

macOS is required for the Seatbelt sandbox; the suite is offline (no model or network call).

```sh
uv sync --dev
uv run pytest
uv run assay --version
```

CI runs the same suite on `macos-latest`.

## Docs

- [`VISION.md`](VISION.md) — the thesis, the moat, non-goals.
- [`CLAUDE.md`](CLAUDE.md) — guardrails and the verdict contract.
- [`ETHICS.md`](ETHICS.md) — the audit ethics, disclosure and correction policy.
- [`docs/audit/PROTOCOL.md`](docs/audit/PROTOCOL.md) — the audit protocol and checklist.
- [`docs/ROADMAP.md`](docs/ROADMAP.md) — phased plan and risk register.
- [`docs/technical/CAPABILITY_ROADMAP.md`](docs/technical/CAPABILITY_ROADMAP.md) — A1..A10 capabilities in build order.
- [`docs/technical/ARCHITECTURE.md`](docs/technical/ARCHITECTURE.md) — the design.

## Lineage

Assay is one of three siblings scaffolded together on 2026-10-22 (with [Tenon](../tenon) and
[Pry](../pry)), out of a market-demand research pass, sharing house DNA with
[Belay](../belay), [Plumb](../plumb), and [Whetstone](../whetstone). Standalone by design — no
code dependency on sibling projects yet.
