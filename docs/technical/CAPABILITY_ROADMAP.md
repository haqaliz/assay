# Assay: Capability Roadmap

Engine capabilities in build order. Each lands test-first. A1–A5 are built and composed by the
`assay check` CLI (M1.4); the rest are not.

| ID | Capability | Depends on | Guardrail tie-in |
|---|---|---|---|
| **A1** | **Skill ingest and declared-scope extraction.** Parse a skill (Claude Code `SKILL.md` first) into a typed record: name, description, declared tools, declared file and network scope. Malformed input is a named refusal. *(built: `src/assay/ingest/`)* | none | A skill is data, never executed at parse time |
| **A2** | **Sandbox.** Isolated jail: filesystem confined, network deny-by-default (allowlist per run), no real credentials or env vars, resource and time limits. *(built: `src/assay/sandbox/`)* | none | Constraint 2: nothing real is reachable |
| **A3** | **Agent driver (BYOK).** Run a real agent with the skill loaded, against one task derived from the skill's stated purpose; every tool call runs in the sandbox. Cost caps. *(built: `src/assay/agent/`; the manual BYOK gate run is still unperformed — no key in CI)* | A1, A2 | BYOK only; no consumer-subscription automation |
| **A4** | **Behavior capture and diff.** Record file, network, shell and instruction events as content-addressed traces; diff observed against declared scope. Does not assign a verdict; A5 owns that. *(built: `src/assay/capture/`)* | A2, A3 | Observation, not inference |
| **A5** | **Verdict and strictness.** `CLEAN/FLAGGED/MALICIOUS/UNVERIFIED`. Four finding classes: undeclared file access, undeclared network, shell execution, hidden or injected instructions. Strictness is user-raisable; a floor cannot be lowered. *(built: `src/assay/verdict/`; the shell and instruction pattern lists are deliberately narrow and uncalibrated until A7)* | A4 | Constraints 3 and 4 |
| **A6** | **Signed attestation bundle.** Hash-listed record of skill hash, sandbox config, traces, verdict; verifiable by a third party. | A5 | Pattern copied from Plumb, not imported |
| **A7** | **Findings corpus and benchmark.** Labeled malicious and clean samples; precision and recall with denominators and label authority. | A5, A6 | Measure against human labels |
| **A8** | **Format adapters.** OpenClaw/ClawHub, Cursor rules, MCP server manifests, others as warranted. | A1-A5 | One at a time |
| **A9** | **Registry and install-time layer (hosted).** Pre-listing check, `assay install` gate. | A5-A7 | Opt-in, BYOK |
| **A10** | **Optional static pre-filter.** Cheap triage that can prioritize runs but never assigns a verdict above `UNVERIFIED`. | A1 | Constraint 1 |

## Sequencing

A1 and A2 can start in parallel. A3 needs both. A4 and A5 follow. A6 and A7 prove the result.
A8 widens coverage after the core is trusted. A9 is the business and is deferred.

## Open questions

- Which synthetic-task strategy reliably triggers a skill's declared behavior? This decides how
  often R1 bites. Needs a spike in Phase 0.
- Can any provider's subscription be driven legitimately? Check terms before designing for it.
