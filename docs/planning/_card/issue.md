# feat verdict-floor — A5: Verdict and strictness

## Brief

> Build A5, the verdict and strictness layer, for Phase 1 milestone M1.3 in `docs/ROADMAP.md`: map an
> A4 `Diff` (plus the trace it came from) to exactly one of `CLEAN`, `FLAGGED`, `MALICIOUS`,
> `UNVERIFIED`, with a named cause and a list of findings. Four finding classes are always checked:
> undeclared file access, undeclared network, shell execution, and hidden or injected instructions.
> Strictness levels (`baseline`, `standard`, `strict`) change which findings block; a floor defines
> a minimum severity per class and config that tries to go below it is rejected at load.
> `MALICIOUS` requires a captured, reproduced behavior and always carries `review_required`.
> `CLEAN` requires that every dimension was declared and nothing exceeded it; an empty or
> no-trigger run is `UNVERIFIED`, never `CLEAN`. `UNDECLARED` divergences (the skill declared
> nothing for that dimension) cannot by themselves produce `MALICIOUS`. Instructions are recorded by
> A4; the instruction finding is a candidate-level signal capped below `MALICIOUS`, because a static
> read may flag but may not decide. No CLI (M1.4), no bundle (A6), no corpus (A7).

Source: chosen by `assay-next` as the next capability after A1–A4 shipped (`CAPABILITY_ROADMAP.md`
A5 depends on A4; it retires R2 and enforces `CLAUDE.md` constraint 3).

## Context carried from the pick

- `docs/technical/CAPABILITY_ROADMAP.md` A5: *"Verdict and strictness. `CLEAN/FLAGGED/MALICIOUS/
  UNVERIFIED`. Four finding classes … Strictness is user-raisable; a floor cannot be lowered."*
- `docs/ROADMAP.md` M1.3 and R1/R2; the gate still needs a real keyed run.
- `CLAUDE.md` constraint 3 (the floor) and constraint 4 (do not over-claim; `MALICIOUS` needs a
  captured, reproduced behavior; `UNVERIFIED` is never rendered `CLEAN`).
- `docs/technical/ARCHITECTURE.md`: a verdict re-derives from the trace alone; `UNVERIFIED` causes
  are `WONT_PARSE`, `SANDBOX_FAILED`, `AGENT_FAILED`, `COST_CAPPED`, `NO_TRIGGER`,
  `TRACE_INCOMPLETE`.
- Shipped A4: `Diff` carries `Divergence(kind, target, status, outcome, reason, denials)`, coverage
  per dimension, and refuses a trace from a different skill. `DivergenceStatus` is
  `EXCEEDED | UNDECLARED`.
