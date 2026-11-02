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
declared scope or full skill body yet, so replay is the first follow-on.

**M2.2 labeled corpus and benchmark (2026-11-03).** A7 shipped: `corpus/` holds 20 labeled cases
(9 malicious, 11 clean; 18 synthetic, 2 stored local-model runs) and `assay corpus corpus/` scores
A5 against them offline, with explicit numerators and denominators. Result on this corpus: malicious
precision 1.00 (5/5), malicious recall 0.71 (5/7), detection recall 1.00 (7/7), clean
false-`MALICIOUS` 0.00 (0/6), clean review 0.33 (2/6), coverage 0.65 (13/20); all five `UNVERIFIED`
causes appear. The `plumb-report` regression is `FLAGGED`, not `MALICIOUS`; the `plumb-begin-fast`
re-run produced no tool actions and is `UNVERIFIED/NO_TRIGGER`. 742 offline tests. A5 is unchanged:
this slice measures, it does not tune. The corpus is single-labeled and synthetic-dominated, so the
numbers are a regression signal, not a population estimate. Next: the M2.3 public audit (after
`ETHICS.md`, R3) or the first A8 adapter.

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
| M2.3 | Public audit of top N skills | Findings reviewed, authors/registries notified before publication (see R3) |
| M2.4 | Adapters: OpenClaw/ClawHub, Cursor rules, MCP | One at a time, in that order, each behind its own test fixtures |

## Phase 3: Hosted/registry layer (after the 3-month window)

Registry pre-listing check, install-time gate (`assay install`), managed scanning (BYOK, opt-in).
Not scheduled; depends on Phase 2 results.

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
| R8 | Scope sprawl across formats | High/Med | One adapter at a time; Claude Code `SKILL.md` ships first |
| R9 | Slow adoption | Med/Med | Public audit as the credibility play; GitHub Action for skill authors |
