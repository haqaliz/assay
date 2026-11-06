# Assay: Project Context for Claude Code

This file orients a coding agent working in this repository. Read it first. Deeper context
lives in the `docs/` folder.

---

## What this project is

**Assay** is an **execution-grounded security verifier for AI agent skills**. Point it at a
skill (a Claude Code `SKILL.md`, an OpenClaw/ClawHub skill, a Cursor rule, or similar; MCP servers
are a separate, deferred capability), and Assay runs it in a sandbox against a real agent, captures
exactly what it did
(files touched, network calls made, shell commands run, instructions it tried to inject), and
compares that observed behavior against what the skill *declares* it does. It returns a
**per-skill verdict** backed by a captured record of the run — never a guess from reading the
markdown.

The name: to *assay* a metal is to test its purity by actually putting it through a process, not
by looking at it. Assay asks of a skill: *does it do only what it says it does, when you actually
run it?*

Status: **A1–A7 exist, plus two A8 adapters (OpenClaw/ClawHub and Cursor rules) and the A10 static
pre-filter; nothing else.**
Ingest (`src/assay/ingest/`) turns a Claude Code or OpenClaw/ClawHub `SKILL.md`, or a Cursor `.mdc`
project rule, into a frozen `Skill` record with a tri-state declared `Scope` (undeclared vs declared
none), a `format`, and declared `requirements`/file scope (OpenClaw `metadata.openclaw`; Cursor
`globs`/`alwaysApply`), refusing malformed input with a named cause. The sandbox (`src/assay/sandbox/`) runs a command
under macOS Seatbelt with confined writes, port-scoped network, a scrubbed env and CPU/wall limits.
The agent driver (`src/assay/agent/`) runs a bounded model loop: the model runs outside the jail,
every tool call runs through the sandbox, and the result is actions, usage and cost with a named
stop cause — never a verdict. Two providers share the `Model` seam: Anthropic (BYOK) and
OpenAI-compatible (keyless local Ollama; a non-local base URL must be https and needs
`ASSAY_API_KEY`). Capture (`src/assay/capture/`) turns that outcome into a
canonical, content-addressed trace of file, network, shell and instruction events, stores it
atomically as `<sha256>.json`, and diffs observed events against the skill's declared scope while
keeping "undeclared" and "declared none" distinct. The verdict layer (`src/assay/verdict/`) turns
that diff into exactly one `Assessment`: a `CLEAN/FLAGGED/MALICIOUS/UNVERIFIED` verdict, findings
with severity and evidence, a named `UNVERIFIED` cause, and a `blocked` flag from the chosen
strictness. `MALICIOUS` needs a `HIGH` finding from a captured `OK`/`DENIED` action; an
instruction-pattern match is capped at `REVIEW` and can never produce it. Strictness changes only
what blocks; the four-class floor cannot be lowered. `assay check <skill>` (`src/assay/cli/`)
composes A1–A5 into one command with a verdict-only exit code and a canonical JSON report; before any
spend it refuses an OpenClaw skill the jail cannot satisfy (`UNVERIFIED/REQUIREMENTS_UNMET`), and the
report carries the skill `format` and `requirements`. The
bundle layer (`src/assay/bundle/`) turns a saved trace plus its `SKILL.md` into one canonical,
SSH-signed record — exact skill source, skill hash, trace, sandbox config hashes, assessment — and
`assay verify` checks every hash and the signature offline, re-parses the embedded source and re-runs
the shipped `assess`, refusing a signed assessment that does not follow (`replay: verified`). It
attests that the record is intact, who signed it, and that the verdict follows from the recorded
inputs; it does not prove the run was captured honestly or that the skill is safe. The
corpus layer (`src/assay/corpus/`, `corpus/`) holds 20 labeled cases (18 synthetic, 2 stored
local-model runs), and `assay corpus <dir>` re-runs A5 over them offline, reporting precision and
recall with explicit denominators, false-`MALICIOUS` ids and `UNVERIFIED` coverage by cause. It
measures A5; it does not tune it. The corpus is single-labeled and synthetic-dominated, so those
numbers are a regression signal, not a population estimate. A separate private 8-case real control
(`corpus/real/`) holds one local-model run of each of the maintainer's own Plumb skills, all labeled
clean; it is a false-positive and coverage control, not a benchmark or an audit. The A5 shell list
was calibrated on a separate held-out set with four `HIGH` patterns (`dd` to a device, `pty.spawn`,
`/dev/tcp/`, `socat` shell); the instruction list was calibrated on its own 8-case held-out set
(five patterns added, two narrowed), taking detection from 0/4 to 4/4 and clean review from 2/4 to
0/4 with no false `MALICIOUS`. It is still narrow and capped at `REVIEW` — strict `MALICIOUS` recall
stays 0/4 by design — and the 20-case benchmark is unchanged. The A10 static pre-filter (`assay
triage`) ranks a skill's text with `priority`/`signals` only; it has no verdict, findings, trace or
run, and its list is uncalibrated.
CI runs the offline suite on macOS; `assay --version` reports the installed version; `0.1.0` is the
first PyPI release, published by the `v0.1.0` tag through Trusted Publishing. The audit gate
(`ETHICS.md`,
`docs/audit/`) is in place; no third-party audit has run or been published, and a public finding
needs a second reviewer and the disclosure window. A private own-skill runner dry run was executed on
2026-11-06; it was not reviewer-signed and publishes nothing. MCP server verification is a separate
capability,
not an A8 adapter; it is deferred after the design spike (a manifest parser would be a static scan).
The suite is offline on synthetic outcomes, the corpus and a local `ssh-keygen`; the Phase 0 gate ran
a local model on 2026-10-31, and the first real Anthropic-keyed run has not happened. Do not describe
capability that isn't there.

Lineage: Assay is one of three siblings scaffolded together on 2026-10-22 (with Tenon and Pry),
drawn from a market-demand research pass (`~/dev/at/ideas/market-demand-2026-10.md`) and sharing
house DNA with Belay, Plumb, and Whetstone. It is **standalone** — no code dependency on Belay's
sandbox or bundle machinery, though the pattern is reused. Abstractions get extracted into a
shared package only once a second project actually needs the same thing, not before.

---

## The wedge (read this before proposing any feature)

There are two things you could build. Know which one you are touching.

- **Reading a skill's markdown and guessing whether it's safe.** Static pattern matching:
  flagging keywords, scanning for shell commands textually, an LLM opining "this looks sketchy."
  CROWDED and easy to fool — a skill's most dangerous instructions can be plain English with no
  code to scan at all, and a 2026 study found metadata-only attacks bias agent selection 77.6%
  of the time and evade governance classifiers in up to 100% of cases. **We do NOT build this as
  the verdict.**
- **Running the skill for real, in a sandbox, against a real agent, and diffing what it actually
  did against what it declares.** Capture every tool call, file access, network call, and shell
  command; compare that to the skill's stated scope. **This IS the company.**

Static analysis (NVIDIA's open-source SkillSpector) already exists and is useful — it's a cheap
first pass, not the verdict. Assay's moat is the part SkillSpector cannot do: proving what a
skill *did*, not what its text *looks like* it might do.

---

## Key strategic constraints (do not violate)

1. **Execution decides, never a bare static or LLM judge.** A static scan or a model reading the
   skill's markdown may *flag a candidate* or *triage priority* (`assay triage`). Only an actual
   **sandboxed run, observed and captured**, may produce a verdict above `UNVERIFIED`. If a design lets a pattern
   match or a model's opinion stand in for an observed behavior, stop and flag it.
2. **No real secrets, no real user data, in the sandbox.** The sandbox that runs an untrusted
   skill is isolated: filesystem jail, network allowlist/deny-by-default, no real credentials.
   A skill being tested must never be able to reach anything that matters.
3. **A floor that cannot be lowered.** Four finding categories — undeclared shell execution,
   hidden/injected instructions, undeclared network calls, undeclared file access — are always
   checked, at a minimum severity, regardless of the user's chosen strictness. A user may raise
   strictness; no setting may disable the floor.
4. **Do not over-claim — this is the whole product.** `CLEAN` means *observed behavior in this
   run matched declared scope*, not "this skill is safe forever" or "this skill has no bugs." A
   skill whose dangerous behavior only triggers conditionally (a time bomb, a specific prompt)
   and didn't trigger in this run is `UNVERIFIED`, never `CLEAN`. `MALICIOUS` requires a
   reproduced, captured behavior — never a static-only inference.
5. **Build the part that gets BETTER as foundation models improve.** A stronger base model, used
   as the sandboxed agent, surfaces a skill's real behavior more completely — making Assay
   sharper, never making the observed-behavior verdict redundant.
6. **Responsible disclosure before publication.** Any third-party audit follows `ETHICS.md` and
   `docs/audit/PROTOCOL.md`: captured evidence, three private runs, a reviewer who did not run the
   skill, a 30-day disclosure window (7 days for active exploitation), and a correction path. A
   `MALICIOUS` finding on a real public skill is reviewed before publication, and the
   author/registry gets a chance to respond (R2/R3). Until a second reviewer is named, audits stay
   private and nothing is published.
7. **Test-first.** Every capability lands with its failing test written first.

---

## The verdict contract (referenced throughout)

Per-skill, per-run, deliberately conservative.

| Verdict | Meaning | May be emitted when |
|---|---|---|
| **CLEAN** | Observed behavior matched declared scope, at the user's chosen strictness | The skill ran in the sandbox and nothing it did exceeded what it declared |
| **FLAGGED** | Observed behavior includes a finding, but below the user's "block" threshold | A finding fired above the floor but the user's strictness treats it as review-worthy, not fatal |
| **MALICIOUS** | Observed behavior reproduced a known-bad pattern (exfiltration, destructive execution, instruction injection attempting to override agent policy) | The sandbox captured it directly — never inferred from text alone |
| **UNVERIFIED** | We could not decide | The skill wouldn't run in the sandbox, the harness crashed, the run was cost-capped, or the dangerous path never triggered — the honest default |

A static scan or model may flag a candidate; **the sandboxed, observed run** assigns the verdict.
`UNVERIFIED` is never rendered as `CLEAN`.

---

## Tech direction

- **Python core** (via `uv`), CLI-first (`assay`), self-hostable OSS engine; a hosted/registry
  layer comes later. Exact stack details live in `docs/technical/ARCHITECTURE.md`.
- **Observation primary path is BYOK**: the user supplies their own model API key, and Assay
  drives a real agent inside the sandbox against synthetic tasks designed to trigger the skill's
  declared behavior. Running against a consumer chat *subscription* instead of an API key is an
  **open question, not a design assumption** — most providers' consumer terms prohibit automating
  a subscription this way. Do not build toward it without re-confirming it's permitted; default
  to BYOK API keys only.
- Format coverage starts with Claude Code `SKILL.md` (narrowest, best understood); the
  OpenClaw/ClawHub `SKILL.md` and Cursor rules adapters are built. MCP server manifests are not a
  file adapter: a server is a long-lived program, so verification is a separate capability, deferred
  after the design spike. Other file-based formats follow as they prove worth supporting — see
  `docs/technical/CAPABILITY_ROADMAP.md` for the build order.
- Pinned versions, deterministic sandbox setup, content-addressed captured traces, and a signed
  attestation bundle are core requirements, not nice-to-haves.
- Capture every (skill, observed behavior, verdict) into a findings corpus wherever feasible —
  it's the compounding evaluation dataset and part of the moat.

---

## Founder profile

Solo / small team. Full-stack developer + ML engineer. No prior registry/marketplace
relationships — the moat is engineering (sandbox + observed-behavior diffing), not partnerships.

---

## Folder / docs structure

```
README.md                          # Repo front door
VISION.md                          # Narrative thesis, moat, non-goals
CLAUDE.md                          # This file
ETHICS.md                          # Audit ethics, disclosure and corrections
CHANGELOG.md                       # Unreleased history
LICENSE                            # Apache-2.0
.github/workflows/ci.yml           # macOS offline suite
docs/
  ROADMAP.md                       # Phased plan + risk register
  technical/CAPABILITY_ROADMAP.md  # A1..A10 engine capabilities in build order
  technical/ARCHITECTURE.md        # Design: ingest → sandbox run → capture → diff → verdict → bundle
  audit/                           # Protocol, finding template and gate status
  planning/{slug}/                 # In-flight PRDs, specs, and plans (per unit of work)
```

Consult the relevant file before non-trivial decisions, and keep docs in sync when direction
changes.

---

## Quick facts for grounding (do not fabricate beyond these)

- Snyk's ToxicSkills audit scanned 3,984 skills across ClawHub and skills.sh (2026-02-05): 13.4%
  (534) had at least one critical issue, 36.8% (1,467) had a flaw of any severity, 76 confirmed
  malicious payloads.
- The ClawHavoc campaign planted 1,184+ malicious skills on ClawHub distributing the Atomic
  macOS Stealer; 5 of the 7 most-downloaded skills at peak infection were confirmed malware.
- skills.sh listed ~670,000 skills as of June 2026; SkillsMP lists ~1.9M scraped from GitHub.
- NVIDIA's open-source SkillSpector scanner found 26.1% of a 31,132-skill subset vulnerable and
  5.2% showing likely malicious intent — static-only; a clean scan doesn't mean a skill is safe.
- A metadata-only attack biased agent skill selection 77.6% of the time and evaded governance
  classifiers in 36.5%–100% of cases (cited 2026 study).
- OWASP published an Agentic Skills Top 10.

If you need a statistic that isn't here, do not invent one; say it's unverified.

## graphify

If a `graphify-out/` directory ever appears in this repo, treat codebase/architecture/
file-relationship questions as graphify queries first (`graphify query`, `graphify explain`,
`graphify path`; graph at `graphify-out/graph.json`) before grep/read, per the global CLAUDE.md.
