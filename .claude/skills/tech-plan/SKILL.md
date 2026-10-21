---
name: tech-plan
description: Create a phased technical implementation plan from planning artifacts in docs/planning (PRD + aspect spec). Use after prd-interview when ready to execute a specific aspect. Triggers on "tech plan", "implementation plan", "plan from PRD".
tags:
  - planning
  - documentation
metadata:
  status: trial
---

Create a phased technical implementation plan from planning artifacts under `docs/planning/{slug}/`.
Inputs can come directly from `prd-interview`; do not require `prd-generator`.
This is Phase 5 of `assay-begin-fast` — the plan it produces is executed in Phase 6 through the agents team under strict TDD.

If the user provided artifacts in context, use them directly. Otherwise, search:

- PRDs matching `docs/planning/*/prd.md`
- Aspect specs matching `docs/planning/*/*/spec.md`

Analyze the current codebase, then create a detailed **Implementation Plan**.
Assay is **greenfield**: today the authoritative reading is `docs/technical/CAPABILITY_ROADMAP.md`
(A1..A10, dependencies, guardrail tie-ins), `docs/technical/ARCHITECTURE.md` (the design), and
`docs/ROADMAP.md` (phases, milestones, R1..R9); the engine will live under `src/assay/` once it exists.

## Handoff Contract

- **Feature requirements source:** `docs/planning/{slug}/prd.md`
- **Aspect requirements source (preferred):** `docs/planning/{slug}/{aspect}/spec.md`
- **Plan output (required):** `docs/planning/{slug}/{aspect}/plan_YYYYMMDD.md`

Plan one aspect at a time.

## Deliverables

### 1. Project Setup Checklist

- Directory/module structure under `src/assay/`, `tests/`.
- Configuration (pyproject entries, env, sandbox limits).
- Dependencies via `uv add`.
- **Greenfield:** if `pyproject.toml` / `uv.lock` / `src/` don't exist, scaffolding them is part
  of the plan's first phase — say so explicitly. Test-first still holds.

### 2. Implementation Phases

For each phase: Goal, Prerequisites, Files to create/modify, Validation (`uv run pytest <path>`),
Commit message. Each phase is a unit the agents team can own end-to-end under TDD.

### 3. File-by-File Build Order

Filepath, one-line purpose, key exports, dependencies.

### 4. Testing Strategy

- Unit tests mapped to phases, written first.
- Integration tests. Manual verification steps.
- **Start from the capability's acceptance intent.** `CAPABILITY_ROADMAP.md` and the aspect
  `spec.md` state what each capability must do; lift those into tests before the code. Sandbox
  and agent-driver tests are deterministic and **run with no real sandbox and no real model
  call** — any live run sits behind an injectable seam using recorded traces in CI.

### 5. Environment & Determinism

- Env vars (BYOK keys stay in `.env`, never committed, never a default).
- Local setup: `uv sync`.
- A verdict must be re-derivable from the signed bundle alone. A test whose result depends on
  clock, network, or random ordering is a bug in the plan.

### 6. Edge Cases & Error Handling

- Given Assay's contract, name the explicit `UNVERIFIED` cause for anything that can fail to
  evaluate (`WONT_PARSE`, `SANDBOX_FAILED`, `AGENT_FAILED`, `COST_CAPPED`, `NO_TRIGGER`,
  `TRACE_INCOMPLETE`). A harness-side failure is `UNVERIFIED`, never `MALICIOUS`.

### 7. Agent Execution Notes

- Checkpoints for human review, areas likely to need iteration, where the agent should ask for clarification.

## Guidelines

- Be extremely explicit. Prefer small, testable increments.
- Each phase should result in runnable (even if incomplete) code, suite kept green.
- Don't plan work that rests on a static pattern match or a model opining on a skill's text as
  the verdict — flag it against `CLAUDE.md`'s wedge; the sandboxed, observed run decides.
- Respect the capability build order: A3 needs A1+A2; A4 needs A2+A3; A6/A7 need A5; A9 needs
  A5-A7. Abstractions are earned by the second implementation, not designed for the first.

## Edge Cases

- **Greenfield vs. existing codebase**: For greenfield, include full setup.
- **No aspect spec exists yet**: Derive candidates from the PRD, ask the user to choose, draft `spec.md`, confirm, then plan.
- **Incomplete PRD**: If it lacks testable acceptance criteria, flag it and recommend `prd-interview`.
- **Multiple PRDs**: Separate plans unless they share infrastructure.
- **PRD with flagged gaps**: Note these in the plan and recommend resolution before the affected phase.
