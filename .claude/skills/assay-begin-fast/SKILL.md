---
name: assay-begin-fast
description: Use when starting work on an Assay unit of work (a GitHub issue id or an inline brief) and you want the fast path straight to an implementation plan. Triggers on "assay-begin-fast", "abf", "abf bug 12", "abf feat skill-ingest", "begin fast".
arguments: "type id"
---

# Assay Begin (Fast Track)

## Overview

Turn a single unit of work into shipped, test-driven code. The fast track is:
**isolate → gather → dig → PRD → plan → implement (TDD).** No proposal/diagram
deliverables (use `assay-begin` / `ab` when you need those).

**Two non-negotiables:**
- **Always work through the agents team.** Every phase with independent units of
  work is dispatched to agents and synthesized.
- **Implementation is always test-first**, via `superpowers:test-driven-development`,
  executed by the agents team.

**Invocation:** `abf <type> <id>` — e.g. `abf bug 12`, `abf feat skill-ingest`.

- `type` ∈ `bug | feat | feature | task | chore` (normalize `feature` → `feat`).
- `id` = a **GitHub issue number** when one exists, otherwise a short descriptive **slug**.
- Owner is `aliz`.

## Task source: GitHub issue, tolerate absence

The repo exists on GitHub but likely has no issues filed yet. Expect the fallback path:

- If `id` is numeric and `gh issue view <id>` succeeds → use it as the source.
- Otherwise → ask the user for a one-paragraph **inline brief**.

## Pipeline

### Phase 0 — Isolate in a worktree

**REQUIRED SUB-SKILL:** Use `assay-worktrees`.

- Branch: `<type>/<id>/aliz`. Worktree dir: `.claude/worktrees/<type>-<id>`.
- Create from `master` — Assay's base branch is **`master`**. Prefer `origin/master`;
  fall back to local `master` if the remote ref isn't fetched.
- **Greenfield:** `uv sync` fails until `pyproject.toml` exists. If your work *is*
  the scaffolding, the failing test comes first.

### Phase 1 — Gather context (`gh`, or inline brief)

Save a raw dump to `docs/planning/_card/issue.md` in the worktree. If no issue is
reachable, write the inline brief under a **Brief** heading.

### Phase 2 — Deep dig

- Read the saved dump.
- Map the relevant code paths. Assay is **greenfield** — today "code paths" means
  `docs/technical/CAPABILITY_ROADMAP.md` (A1..A10), `docs/technical/ARCHITECTURE.md`,
  and `docs/ROADMAP.md`. Once the engine exists it lives under `src/assay/`.
- Produce a short written understanding note: what's really being asked, affected
  areas, ambiguities, open questions.
- Honor `CLAUDE.md`'s constraints: execution (a sandboxed, observed run) decides the
  verdict, never a static scan or a model's opinion. The floor finding classes
  cannot be lowered. No real secrets or user data ever reach the sandbox.
- Place the work in the pipeline (A1 ingest, A2 sandbox, A3 agent driver, A4 capture
  and diff, A5 verdict, A6 bundle, A7 corpus, A8 adapters, A9 hosted, A10 static
  pre-filter).

### Phase 3 — Requirements interview

**REQUIRED SUB-SKILL:** `prd-interview`. Confirm a descriptive kebab-case slug.
Output: `docs/planning/{slug}/prd.md` (+ aspect `spec.md` if decomposed).

### Phase 4 — Generate & self-critique the PRD

**REQUIRED SUB-SKILL:** `prd-generator`.

### ⛔ Review gate — STOP

Present the PRD and its flagged gaps. Wait for explicit approval.

### Phase 5 — Implementation plan

**REQUIRED SUB-SKILL:** `tech-plan`. One aspect at a time. Output:
`docs/planning/{slug}/{aspect}/plan_YYYYMMDD.md`.

### Phase 6 — Implement (TDD, agents team)

**REQUIRED SUB-SKILL:** `superpowers:test-driven-development` — strict RED → GREEN
→ REFACTOR.
**REQUIRED SUB-SKILL:** `superpowers:subagent-driven-development` — one agent per
independent task; parallelize with `superpowers:dispatching-parallel-agents`.

- Run `uv run pytest` after each task; keep the branch green. Sandbox and agent-driver
  tests run offline with recorded traces — no real sandbox escape attempt and no real
  model call in CI.
- Commit per task on `<type>/<id>/aliz`.

## Artifact layout (inside the worktree)

```
docs/planning/
├── _card/issue.md
├── {slug}/prd.md
└── {slug}/{aspect}/plan_*.md
```

## Agents team (mandatory)

**REQUIRED SUB-SKILL:** `superpowers:dispatching-parallel-agents` /
`superpowers:subagent-driven-development` (Phase 6).

## Common mistakes

| Mistake | Fix |
|---|---|
| Working in the primary checkout | Create the Phase 0 worktree first |
| Branching from anything but `master` | Assay's base branch is `master`; prefer `origin/master` |
| Slug = `bug-12` | Use a descriptive slug; the id stays in branch/PR |
| Treating a missing `pyproject.toml` as fatal | Greenfield — scaffold it, test-first |
| Skipping the review gate | PRD must be approved before tech-plan |
| A verdict from a static scan or model opinion | Stop and flag — only the sandboxed, observed run decides |
| Implementing serially | Execute through the agents team |
