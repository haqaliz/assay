---
name: assay-next
description: Use when deciding what to build next in Assay and you want the single highest-leverage capability picked from the repo's own roadmap and planning files (not invented), grounded in the moat and in what has already shipped or been deferred, ending with a ready-to-run handoff. Triggers on "assay-next", "an", "what's next", "next feature", "pick next".
arguments: ""
---

# Assay Next (pick the most important capability)

## Overview

Read the repo's own roadmap and planning files, rank the real candidate capabilities
against the moat and against what has shipped or been deferred, and recommend the
single highest-leverage one to build next. End with a ready-to-paste
`assay-begin-fast` invocation so the next session can start that worktree.

This skill RECOMMENDS and hands off. It does NOT create a worktree or start
`assay-begin-fast` itself; the user runs the handoff prompt when ready.

## When to use

- "what should I build next", "pick the next capability", at the start of a session.
- After a merged capability or a phase gate, when choosing the next unit of work.
- Not for: executing a chosen capability (use `assay-begin-fast`), or planning an
  already-chosen one (use `prd-interview` / `tech-plan`).

## The candidate set is the FILES, never invented

Read these (the source of truth, in this order). Assay is **greenfield**, so the
planning docs carry almost all the signal today — but code, once it exists, wins
over prose:

- `docs/technical/CAPABILITY_ROADMAP.md`: the **A1..A10** engine capabilities in build
  order, each with what it does, its dependencies, and its guardrail tie-in. This
  is the primary candidate set.
- `docs/ROADMAP.md`: the phases (0–3), the milestones, and the **R1..R9 risk
  register**. A candidate that retires a High-likelihood/High-impact risk is worth
  more than its slot suggests.
- `CLAUDE.md` and `VISION.md`: the wedge, the moat, and the guardrails the pick must obey.
- `docs/technical/ARCHITECTURE.md`: the ingest → sandbox → capture → diff → verdict →
  bundle design.
- `docs/planning/*/`: in-flight, completed, and deferred work, once any exists.
- `git log` / `git tag` / the test suite: what actually shipped. Trust this over
  prose. **Today there are no commits beyond the scaffold** — say so plainly.

If a file above is missing, still reference it by path and say it isn't written yet.
Never substitute memory for a file you couldn't read.

## How to rank (grounded in CLAUDE.md)

1. **Execution-grounded verdicts only.** A candidate that lets a static scan or a
   model's opinion stand in for an observed sandbox behavior is dropped.
2. **Respect the build order and its dependencies.** A2/A3 need A1+A2; A4 needs A2+A3;
   A6/A7 need A5; A8 widens formats only after the core is trusted. The next
   capability is usually the lowest unshipped ID whose dependencies are met.
3. **The sandbox and the floor are the critical path.** A2 (sandbox) and A5
   (verdict/floor) are the moat (R4/R2). Nothing downstream is trustworthy without them.
4. **Deepen the corpus.** Favor work that feeds the findings corpus (A7) wherever feasible.
5. **The gate beats the feature.** Before Phase 0's gate (one real skill run end to
   end, with an observed behavior that differs from a declared one), the
   highest-leverage work is whatever produces that gate.
6. **Follow-on slices count.** A shipped capability's next slice (a new finding
   class, a new strictness level) is a valid candidate.

## Process

1. Read the files above. Build the candidate list: unshipped capabilities whose
   dependencies are met, and follow-on slices of shipped ones.
2. For each candidate, record: shipped-state (cite the file), dependency status,
   moat-leverage, the risk it retires (by R-id), and any known blocker.
3. Rank by the rules above. Pick ONE, plus one or two alternates.
4. Sanity-check the pick against the guardrails and the current phase gate.
5. Produce the handoff (below).

## Output format

- **The pick**: one line naming the capability (with its A-id) and a kebab-case slug.
- **Why**: 2 to 3 bullets tying it to the moat, its dependencies, and what shipped.
- **Alternates**: one or two lines.
- **Known caveat**: the nearest feasibility risk (name the R-id where one applies).
- **Handoff prompt** (ready to paste): an `abf feat <slug>` line plus a 3 to 5
  sentence inline brief including the caveat and the capability's acceptance tests.

## Honesty rules

- Ground every shipped / pending / deferred claim in a named file.
- **Almost nothing has shipped yet.** Say "not started" rather than implying progress.
- If the strongest-looking candidate has a real blocker, say so.

## Common mistakes

| Mistake | Fix |
|---|---|
| Inventing a capability not in the docs | The candidate set is A1..A10 in `CAPABILITY_ROADMAP.md` |
| Recommending a capability whose dependencies are unbuilt | Check the dependency line |
| Re-recommending shipped work | Check `git log` first, not the prose |
| Recommending a static-only verdict | Drop it — execution (the sandboxed run) decides |
| Reaching for A9 (hosted) early | It depends on A5-A7; the core ships first |
| Starting the worktree from this skill | Only recommend and hand off; the user runs `abf` |
