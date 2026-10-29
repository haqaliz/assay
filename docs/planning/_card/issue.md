# feat behavior-capture — A4: Behavior capture and diff

## Brief

> Build A4, behavior capture and diff, for Phase 1 milestone M1.2 in `docs/ROADMAP.md`: turn an A3
> `RunOutcome` into a content-addressed trace of file, network, shell and instruction events, persist
> it under a caller-supplied trace root, and diff those observed events against the A1 `Skill.scope`.
> The trace must be replayable: a verdict can later be re-derived from the trace alone, with no
> re-run and no model call. The diff must preserve A1's tri-state: `None` (the skill declared nothing
> for that dimension) is not the same as `()` (declared to do nothing), and must never be collapsed
> into "clean". The diff reports divergences and coverage gaps; it assigns no verdict (A5 owns
> `CLEAN/FLAGGED/MALICIOUS/UNVERIFIED`). Shell events are compared against the declared tool scope
> (a `Bash` entry), network against `host:port`, files against declared globs. Everything is offline,
> deterministic and tested against fixtures; no CLI, no bundle, no corpus.

Source: chosen as the next capability after A1, A2 and A3 shipped. It is the other half of the
Phase 0 gate ("an observed behavior that differs from a declared one").

## Context carried from the pick

- `docs/technical/CAPABILITY_ROADMAP.md` A4: *"Record file, network, shell and instruction events as
  content-addressed traces; diff observed against declared scope."* Depends on A2, A3. Guardrail:
  *"Observation, not inference."*
- `docs/ROADMAP.md` M1.2: *"File, network, shell and instruction events captured; diffed against
  declared scope; four finding classes"*.
- `docs/technical/ARCHITECTURE.md`: *"Determinism. The agent is non-deterministic, so the replayable
  unit is the recorded trace, not a re-run. A verdict re-derives from the trace alone, and the bundle
  carries the trace."*
- `CLAUDE.md` constraint 4: `CLEAN` only means observed behavior matched declared scope; a skill whose
  dangerous path never triggered is `UNVERIFIED`, never `CLEAN`.
- Shipped: A1 `Skill.scope` (per-dimension `None` vs empty), A3 `RunOutcome.actions` where each action
  carries the `ToolCall` and the sandbox `RunRecord`.
