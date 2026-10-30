# Assay: Architecture

Design intent, not a description of built behavior. **A1 (`src/assay/ingest/`), A2
(`src/assay/sandbox/`), A3 (`src/assay/agent/`), A4 (`src/assay/capture/`) and A5
(`src/assay/verdict/`) are implemented**; everything else below is still intent — verify against
the code and `git log`. A4 records and diffs observed behavior; A5 turns that diff into one
assessment. The manual BYOK gate run is still unperformed.

## Pipeline

```
skill (SKILL.md | ClawHub | Cursor rule | MCP manifest)
        |
        v
  A1 ingest  ---->  Skill record (declared scope)
        |
        v
  A2 sandbox  <----  jail config (fs, network, env, limits)
        |
        v
  A3 agent driver (BYOK)  --  one task from the skill's stated purpose
        |
        v
  A4 capture  ---->  content-addressed event trace (file, net, shell, instruction)
        |
        v
  A4 diff     ---->  observed vs declared
        |
        v
  A5 verdict  ---->  CLEAN | FLAGGED | MALICIOUS | UNVERIFIED  (+ named cause)
        |
        +-->  A7 findings corpus
        v
  A6 signed bundle
```

## Layout

```
src/assay/
  ingest/     A1: parsers per format, Skill record   ← built (Claude Code SKILL.md)
  sandbox/    A2: jail setup, limits, teardown   ← built (macOS Seatbelt)
  agent/      A3: BYOK driver, task generation, cost caps   ← built (Anthropic Messages adapter)
  capture/    A4: event recorder, trace store, diff   ← built (canonical traces, scope diff)
  verdict/    A5: findings, strictness, floor   ← built (assessment, pattern lists)
  bundle/     A6: hash list, signing, verify
  corpus/     A7: labeled cases, metrics
  cli/        assay check | bundle | corpus
tests/        offline; recorded traces; no network, no model calls
```

## Key decisions

- **Sandbox first.** Every skill runs only inside the jail. The jail is the first thing built and
  the most heavily tested; escape attempts are test cases.
- **Observation over inference.** Verdicts above `UNVERIFIED` need a captured event. Static
  signals only order the work.
- **Strictness model.** Levels (for example `baseline`, `standard`, `strict`) change which
  findings block, never the verdict they produce. A hard floor defines minimum severities for the
  four classes; any policy that tries to change it is rejected at construction. An instruction
  match is capped at `REVIEW`, so it can never become `MALICIOUS`.
- **Determinism.** The agent is non-deterministic, so the replayable unit is the *recorded trace*,
  not a re-run. A verdict re-derives from the trace and the strictness policy alone, and the
  bundle carries the trace.
- **Tests run offline.** The agent driver sits behind an injectable seam; CI uses recorded traces.
  No model call and no network in any test.
- **BYOK.** Keys live in the environment of the user, are never committed, and are never defaults.
- **UNVERIFIED causes.** A5 names `NO_TRIGGER`, `NO_DECLARED_SCOPE`, `AGENT_FAILED` and
  `COST_CAPPED`. A skill that will not parse is refused before a trace exists; that refusal needs
  its own mapping when the CLI lands (M1.4).

## CLI shape (target)

`assay check <skill> [--strictness LEVEL] [--max-cost USD] [--out DIR] [--json]`

Exit 0 on `CLEAN`, 1 on `FLAGGED/MALICIOUS/UNVERIFIED`, 2 on usage error. Never a traceback.

## Open questions

- ~~Sandbox technology on macOS and Linux (Seatbelt, containers, or both)~~ **Decided:** Seatbelt
  only, behind a `Sandbox` seam (A2). Docker was rejected as a daemon dependency with no A2
  benefit; the probe evidence and the Linux consequence are in
  `docs/planning/sandbox-jail/prd.md`. A Linux backend is a follow-on slice.
- How to generate synthetic tasks that exercise a skill without an LLM judging the outcome.
- Distribution name on PyPI: `assay` is taken; `assayhq` was free when checked.
