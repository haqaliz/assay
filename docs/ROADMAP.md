# Assay: Roadmap

Goal: **reputation and moat** within roughly 3 months (all three sibling projects run in
parallel, so progress per project is thinner than a solo effort). Form: OSS CLI core first,
hosted/registry layer later. Stack: Python via `uv`.

Milestone order below is my proposal from the capability dependencies; you asked me to order
them after the full roadmap existed. Reorder freely.

**Progress (2026-10-31).** Phase 0 milestones M0.1 (A1) and M0.2 (A2) are shipped, as are Phase 1's
M1.1 (A3), M1.2 (A4), M1.3 (A5) and M1.4 (the `assay check` CLI): 549 offline tests, `A1–A5` in
`docs/technical/CAPABILITY_ROADMAP.md`.

**Phase 0 gate: met on 2026-10-31, with a local model.** `assay check` ran the real
`~/dev/at/plumb/.claude/skills/plumb-next` against `qwen3-coder:30b` on Ollama (no API key, no spend)
and observed two shell commands the skill never declared. Verdict `FLAGGED`, exit 1, trace saved
(`assay-gate-2026-10-31.json` on the maintainer's Desktop). The gate's letter is met; this was not a
Claude run. M0.3 is complete below. The A5 pattern lists remain deliberately narrow; A7 later
measured them on a small synthetic corpus without tuning them.

**M0.3 dogfood (2026-10-31).** All 10 Plumb skills were run against the local model with no key
(`~/Desktop/assay-dogfood-2026-10-31/`). Results: 6 `UNVERIFIED` on a budget stop, 2 `UNVERIFIED`
on a model failure, 1 `FLAGGED`, and 1 false `MALICIOUS` (`plumb-report` writing its report to the
Desktop). The false accusation was fixed the same day: an absolute write is `HIGH` only for a
sensitive location or when a declared file scope was exceeded. Budget stops now report
`UNVERIFIED/BUDGET_LIMIT` instead of `AGENT_FAILED`. No `CLEAN` is possible in this corpus because
none of the skills declares file/network scope.

**M2.1 signed bundle (2026-11-01).** A6 shipped: `assay bundle` turns a saved trace plus its
`SKILL.md` into one canonical, SSH-signed record carrying the skill hash, the trace, the sandbox
config hashes and the A5 assessment; `assay verify` checks every hash and the signature offline
against a caller-supplied public key. Trace schema 2 records the per-action sandbox config hashes.
642 offline tests, including a real `ssh-keygen` round trip on throwaway keys. The bundle proves
integrity and provenance, not that the verdict follows from the trace alone; the trace carries no
declared scope or full skill body yet; the replay follow-on is below.

**A6 replay (2026-11-03).** Bundle schema 2 carries the exact `SKILL.md` source alongside the trace
and assessment. `assay verify` re-parses it, re-runs the shipped `assess` at the recorded strictness,
and refuses a signed assessment that does not follow (`replay-mismatch`); a good bundle prints
`signature: verified` and `replay: verified`. 767 offline tests. Schema-1 bundles are refused as not
replayable. Replay proves the verdict follows from the recorded inputs, not that the run was captured
honestly; a bare trace still does not carry the scope/body and does not replay.

**M2.2 labeled corpus and benchmark (2026-11-03).** A7 shipped: `corpus/` holds 20 labeled cases
(9 malicious, 11 clean; 18 synthetic, 2 stored local-model runs) and `assay corpus corpus/` scores
A5 against them offline, with explicit numerators and denominators. Result on this corpus: malicious
precision 1.00 (5/5), malicious recall 0.71 (5/7), detection recall 1.00 (7/7), clean
false-`MALICIOUS` 0.00 (0/6), clean review 0.33 (2/6), coverage 0.65 (13/20); all five `UNVERIFIED`
causes appear. The `plumb-report` regression is `FLAGGED`, not `MALICIOUS`; the `plumb-begin-fast`
re-run produced no tool actions and is `UNVERIFIED/NO_TRIGGER`. 742 offline tests. A5 is unchanged:
this slice measures, it does not tune. The corpus is single-labeled and synthetic-dominated, so the
numbers are a regression signal, not a population estimate. The M2.3 audit gate and the first A8
adapter followed.

**M2.3 audit gate (2026-11-05).** `ETHICS.md` and `docs/audit/` (protocol, finding template, index)
are in place: captured evidence, at least three private runs, a reviewer who did not run the skill, a
30-day disclosure window (7 days for active exploitation), publication limits, corrections and
records. **No third-party audit has been run or published.** The maintainer is the only reviewer, so
a public finding waits for a second reviewer and the disclosure steps. Docs-only; 767 tests unchanged.
A private own-skill **runner dry run** followed on 2026-11-06; six model-failed cases were re-run on
2026-11-07, for 21 signed bundles, all replayed. Latest per case: 12/15 decided (all `FLAGGED`), 3
`UNVERIFIED`, 0 `HIGH`/`MALICIOUS`. **Reviewer sign-off was recorded privately on 2026-11-10**; it
supports no public finding, and the public-audit gate remains (second reviewer + disclosure).

**M2.4 first adapter — OpenClaw/ClawHub (2026-11-05).** `assay check` accepts an OpenClaw/ClawHub
`SKILL.md`, records its `format` and `metadata.openclaw` requirements, and refuses a skill the jail
cannot satisfy (`requires.env`, `requires.config`, a mismatched `os`, or a required binary absent
from the jail PATH) before any model or sandbox call, with `UNVERIFIED/REQUIREMENTS_UNMET`. A
satisfiable skill runs normally. 828 offline tests. Cursor rules followed on 2026-11-05; MCP is not
built. Most OpenClaw skills declare no file/network/tool scope, so a run stays
`UNVERIFIED/NO_DECLARED_SCOPE` unless `metadata.assay` adds one; the bundle covers `SKILL.md` only,
not the rest of the directory.

**M2.4 second adapter — Cursor rules (2026-11-05).** `assay check` accepts a Cursor project rule
(`.cursor/rules/*.mdc`), maps `alwaysApply`/`globs` to the file scope, and records `format: cursor`.
A write outside the globs is `FLAGGED`; a rule with no findings stays
`UNVERIFIED/NO_DECLARED_SCOPE` because the format declares no tools/network. A Cursor bundle carries
an optional `skill.format` hint so `verify` replays a `.mdc` source, including a description-only
rule; `SKILL.md` bundle bytes are unchanged. 863 offline tests. `AGENTS.md`, `.cursorrules`, and
Cursor user/team rules are out of scope.

**MCP design spike (2026-11-05).** MCP is not a `SKILL.md` adapter: a server is a long-lived
JSON-RPC program (stdio or Streamable HTTP) exposing tools/resources/prompts, and Assay has no MCP
client or long-lived sandbox session. A manifest-only parser would be a static scan in disguise.
Decision: **MCP is reclassified out of A8** as a separate capability (proposed A11, not scheduled).
If pursued, start with a `SandboxSession` + stdio MCP client spike, not a manifest parser; the
verdict would be mostly `UNVERIFIED` because a manifest declares startup, not behavior. No code;
863 tests unchanged. See `docs/planning/mcp-design/prd.md`.

**A5 shell calibration (2026-11-05).** A held-out 8-case shell set (4 malicious, 4 clean) was
measured before and after four new `HIGH` patterns. Before: 0/4 malicious `MALICIOUS` (all `FLAGGED`
on the undeclared-Bash divergence), 4/4 clean `CLEAN`. After: 4/4 malicious `MALICIOUS`, 4/4 clean
`CLEAN`, precision 1.00 (4/4), recall 1.00 (4/4), false-`MALICIOUS` 0/4. The 20-case development
corpus is unchanged (precision 1.00 5/5, recall 0.71 5/7, false-`MALICIOUS` 0/6, coverage 0.65
13/20). 874 offline tests. The held-out set is a one-shot control; a future pattern change needs a
new one. Instruction/network severities, the floor and the verdict contract are unchanged.

**Real-world control (2026-11-05).** A private 8-case control (`corpus/real/`) stores one
local-model run of each of the maintainer's own Plumb skills, all labeled `clean`. Report: 2
`FLAGGED`, 6 `UNVERIFIED` (4 `budget-limit`, 1 `no-trigger`, 1 `agent-failed`), coverage 0.25
(2/8), no false `MALICIOUS`; the 20-case benchmark is unchanged. It is a false-positive and
coverage control, not an audit or a benchmark. 876 offline tests. M2.3 remains gated: no
third-party audit has run or been published.

**A10 static pre-filter (2026-11-05).** `assay triage <skill>` ranks a skill's text with
`priority`/`signals` only; no verdict, findings, trace, model or sandbox. It is optional, its list is
uncalibrated, and it is not the moat: a high priority is not `MALICIOUS` and a low priority is not
safe. 916 offline tests. The execution-grounded run remains the verdict.

**v0.1.0 release (2026-11-07).** `pyproject.toml` is `0.1.0` with PyPI metadata, `CHANGELOG.md`
records the first release, and `.github/workflows/release.yml` publishes a `v*` tag through PyPI
Trusted Publishing (OIDC, no token secret). macOS GitHub Actions runs the offline suite (931 tests)
on the Intel image, and `assay --version` reports the installed package version. `assayhq` 0.1.0 is
published on PyPI (wheel + sdist) and as a GitHub Release. The engine capability roadmap is
complete for A1–A8 (file-based) and A10; A9 (hosted) is deferred, and MCP remains deferred (spike
below). M2.3 remains gated on a second reviewer and the disclosure process.

**Linux sandbox v1 (2026-11-14).** `assay check` runs on Linux under `bubblewrap` (mount/PID/net
namespaces, no daemon) with no sandbox network; `http_get` fails closed with
`UNVERIFIED/SANDBOX_UNAVAILABLE`, while the model runs outside the jail. MCP sessions and a network
allowlist remain follow-ups; Windows uses the same backend via WSL2. The full suite runs on macOS
and Ubuntu 24.04. Released as `0.1.1` on 2026-11-14; the trace/verdict schema and the macOS
Seatbelt path are unchanged.

**MCP spike (2026-11-07).** A long-lived `SandboxSession` and a stdlib stdio MCP client
(`initialize`, `tools/list`, `tools/call`) run against a local fixture inside Seatbelt. Tool calls
are captured as `EventKind.TOOL`; a TOOL-only trace is `UNVERIFIED/NO_TRIGGER`. The fixture proves
inside-root reads and an outside-read denial, a request timeout, and teardown with no orphan. This
was **evidence-only** at the spike: no `Server` record, driver integration, bundle or verdict, and no
MCP claim. 961 offline tests; the floor, cap and trace schema are unchanged. MCP remains deferred.

**MCP server inspector (2026-11-07).** `assay mcp <manifest>` parses a Claude Desktop `mcpServers`
entry into a `Server` record, starts one stdio server in Seatbelt, and reports protocol, tools and
denials. It refuses env values and HTTP; no model, driver, assessment, bundle or verdict. Exit `0`
means "started and listed tools", not safe. 983 offline tests; Stage B followed (below).

**MCP server report (2026-11-08).** `assay mcp-report <manifest> --task ...` registers the server's
tools with the driver (only those tools), runs the task, captures `tools/call` as `TOOL` evidence,
and reports `UNVERIFIED` (no-trigger, no-declared-scope, agent/budget failure) or `FLAGGED`
(instruction text in a tool description/result). There is no `CLEAN`/`MALICIOUS`: a manifest
declares startup, not behavior, and the server's own syscalls are not mediated. Exit `0` means the
report was produced, not safe; no bundle. 1,017 offline tests. MCP verification remains deferred.

**A5 instruction calibration (2026-11-05).** A held-out 8-case instruction set (4 malicious, 4
clean) was measured before and after five patterns were added (`ignore the above`, `disregard
previous`, `forget your instructions`, `keep this between us`, `do not reveal this`) and two were
narrowed (`override your`, `system prompt`). Before: 0/4 malicious detected (all `CLEAN`), 2/4 clean
`FLAGGED`. After: 4/4 malicious `FLAGGED`, 4/4 clean `CLEAN`, detection 1.00 (4/4), clean review
0.00 (0/4), false-`MALICIOUS` 0/4. Strict `MALICIOUS` recall stays 0/4 by design: instruction
findings are capped at `REVIEW`. The 20-case development corpus is unchanged (precision 1.00 5/5,
recall 0.71 5/7, detection 1.00 7/7, false-`MALICIOUS` 0/6, clean review 0.33 2/6, coverage 0.65
13/20). 931 offline tests. The held-out set is a one-shot control; a future pattern change needs a
fresh one. The cap, floor and verdict contract are unchanged.

---

## Phase 0: Prove the wedge (weeks 1-3)

**Gate: one real skill run end to end, with an observed behavior that differs from a declared one.**

| # | Milestone | Done when |
|---|---|---|
| M0.1 | Skill parser (A1) | A `SKILL.md` parses into a typed `Skill` record with declared scope; malformed input is a named refusal |
| M0.2 | Sandbox spike (A2) | A script runs in an isolated jail: no network, writes confined, no real env vars; escape attempts are captured, not allowed |
| M0.3 | Dogfood run | Assay runs the 10 skills in `~/dev/at/plumb/.claude/skills/` and reports results, including its own false positives |

## Phase 1: OSS core (weeks 4-8)

| # | Milestone | Done when |
|---|---|---|
| M1.1 | Real-agent driver (A3), BYOK | A user-supplied key drives an agent in the sandbox against synthetic tasks; cost cap enforced |
| M1.2 | Behavior capture + diff (A4) | File, network, shell and instruction events captured; diffed against declared scope; four finding classes |
| M1.3 | Verdict + strictness levels (A5) — built | `CLEAN/FLAGGED/MALICIOUS/UNVERIFIED`; user raises strictness; the floor cannot be lowered |
| M1.4 | `assay check <skill>` CLI — built | Exit code reflects verdict; JSON output byte-stable |

## Phase 2: Proof and reputation (weeks 8-12)

| # | Milestone | Done when |
|---|---|---|
| M2.1 | Signed attestation bundle (A6) — built | Hash-listed, signed record of a run; a third party can verify it with the signer's public key |
| M2.2 | Labeled corpus + benchmark (A7) — built | Known-malicious samples plus clean ones; precision and recall reported with denominators and label authority |
| M2.3 | Public audit of top N skills — protocol ready; audit not run | Findings reviewed, authors/registries notified before publication (see R3) |
| M2.4 | Adapters: OpenClaw/ClawHub and Cursor rules — built; MCP reclassified out of A8 (deferred) | One at a time, each behind its own test fixtures |

## Phase 3: Hosted/registry layer (after the 3-month window)

Registry pre-listing check, install-time gate (`assay install`), managed scanning (BYOK, opt-in).
Not scheduled; depends on Phase 2 results.

---

## Platform support (Linux v1)

`assay check` runs on Linux under `bubblewrap` (mount/PID/net namespaces, no daemon) with no
sandbox network; `http_get` fails closed with `UNVERIFIED/SANDBOX_UNAVAILABLE`. Windows uses the
same backend via WSL2. MCP sessions and a network allowlist remain follow-ups. CI runs macOS and
Ubuntu 24.04; the plan and remaining risks are in
[`planning/linux-backend/prd.md`](planning/linux-backend/prd.md).

---

## Risk register

| ID | Risk | L/I | Mitigation |
|---|---|---|---|
| R1 | A skill's bad behavior is conditional (time bomb, specific prompt) and never fires in the run | High/High | Verdict is `UNVERIFIED`, never `CLEAN`; synthetic tasks target declared behaviors; report coverage honestly |
| R2 | False `MALICIOUS` on a legitimate skill | Med/High | Require a captured, reproduced behavior; `review_required` on every `MALICIOUS`; harness failure is `UNVERIFIED` |
| R3 | Publishing a finding about a real author or registry without disclosure | Med/High | Disclosure process before any publication; ETHICS.md before the first public audit |
| R4 | Sandbox escape: untrusted skill reaches the host | Low/Critical | Deny-by-default jail, no real credentials, escape tests in the suite, run only in the sandbox |
| R5 | Cost: real-agent runs spend the user's tokens | High/Med | Per-run and per-session caps, scripted-harness mode as a cheap fallback, cost shown before the run |
| R6 | Consumer-subscription automation violates provider terms | Med/High | Default to BYOK API keys only; subscription route stays an open question until terms are checked |
| R7 | SkillSpector or a registry ships overlapping behavioral checks | Med/Med | Differentiate on observed behavior and signed replay; treat static tools as complements |
| R8 | Scope sprawl across formats | High/Med | One adapter at a time; Claude Code, OpenClaw/ClawHub and Cursor shipped; MCP is a separate capability, deferred |
| R9 | Slow adoption | Med/Med | Public audit as the credibility play; GitHub Action for skill authors |
