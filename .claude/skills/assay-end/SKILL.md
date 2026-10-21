---
name: assay-end
description: Use when finishing local work on an Assay unit of work after the PR is merged and you also need a completion report on Desktop. Triggers on "assay-end", "ae", "ae bug 12", "ae feat skill-ingest", "end full".
arguments: "type id"
---

# Assay End (Full Track)

## Overview

Same cleanup as `assay-end-fast`, **plus** a completion report at the end via
`assay-report`.

**Invocation:** `ae <type> <id>` — e.g. `ae bug 12`, `ae feat skill-ingest`.

## Pipeline

**REQUIRED SUB-SKILL:** Use `assay-end-fast` for the cleanup pipeline.

Run its **Phase 0 → Phase 2 exactly as written**. Assay's base branch is **`main`**.
**Phase 3 (release) is deferred.** Only proceed to the report once cleanup
verification passes.

### Phase 4 — Completion report

**REQUIRED SUB-SKILL:** Use `assay-report` with the unit-of-work id and type.

| `ae` arg | `assay-report` arg |
|---|---|
| `bug` | `bug` |
| `task` / `chore` | `task` |
| `feat` / `feature` | `feature` |

### Phase 5 — Comment on the issue (optional)

Same approach as `assay-end-fast` Phase 4. Skip if there's no reachable issue.

## Common mistakes

| Mistake | Fix |
|---|---|
| Running the report before cleanup | Phases 0–2 first |
| Passing the wrong type to `assay-report` | Apply the mapping table |
| Cleaning up against `master` | Assay's base branch is `main` |
| Trying to cut a release during end | Deferred |
