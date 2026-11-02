# feat findings-corpus — labeled corpus and benchmark (A7)

## Brief

Build A7: a labeled corpus of malicious and clean skill runs, plus a benchmark that runs A5 over
it and reports precision and recall with explicit denominators and label authority. Each case
stores the exact `SKILL.md`, a schema-2 trace, and a human label (`malicious` or `clean`) with the
labeler, date, rationale, source (`synthetic` or `local-model`) and the strictness used.
`assay corpus <dir>` verifies each case's skill/trace hashes, re-runs the shipped `assess` at the
recorded strictness, and prints a human or canonical JSON report: decided vs `UNVERIFIED` counts by
cause, a verdict confusion matrix, `MALICIOUS` precision and recall, "any finding" recall, and
false-`MALICIOUS` on clean cases. A zero denominator reports `null`, never `0` or `1`. The first
corpus is synthetic adversarial and clean cases plus the known dogfood regressions (the
`plumb-report` absolute write and a budget stop), not public third-party skills. Labels are
single-labeler (maintainer) and the report says so. No new dependency, no changes to A5's detection
logic or verdict contract, no public audit or disclosure work (that is M2.3/R3).

Source: `docs/technical/CAPABILITY_ROADMAP.md` A7 ("Findings corpus and benchmark"), `docs/ROADMAP.md`
M2.2, and the 2026-10-31 dogfood finding that precision is unmeasured. Selected by `assay-next`
and the A6 handoff on 2026-11-01; A5 and A6 are shipped.

## Context carried from the pick

- A7 depends on A5 and A6; both are built (A6 in PR #9, merge `a48f179`).
- The dogfood left 6/10 `UNVERIFIED`, 1 `FLAGGED`, 1 false `MALICIOUS` (fixed the same day), and no
  `CLEAN` possible because none of the ten Plumb skills declares file/network scope. The stored
  dogfood JSONs are CLI reports; a `traces/` directory of 10 schema-1 traces also exists, and all
  ten skill hashes still match the current Plumb skills.
- `docs/technical/ARCHITECTURE.md`: `corpus/` is A7 ("labeled cases, metrics"); the CLI surface is
  `assay check | bundle | corpus | verify`.
- Constraints: `UNVERIFIED` is never rendered as `CLEAN`; `MALICIOUS` needs a captured behavior and
  `review_required`; the shell/instruction lists stay uncalibrated until this corpus measures them.
- No GitHub issue exists; this card is the source.
