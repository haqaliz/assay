---
name: assay-begin
description: Use when starting work on an Assay unit of work (a GitHub issue id or an inline brief) and you need stakeholder proposals (technical + non-technical PDFs with diagrams) before planning. Triggers on "assay-begin", "ab", "ab bug 12", "ab feat skill-ingest", "begin full".
arguments: "type id"
---

# Assay Begin (Full Track)

## Overview

Same pipeline as `assay-begin-fast`, plus a **proposal phase**: after the PRD is
approved, produce diagrams and two review PDFs (technical + non-technical) for
stakeholders, get approval, then plan.

**Invocation:** `ab <type> <id>` — e.g. `ab bug 12`, `ab feat skill-ingest`.
Arguments and conventions are identical to `assay-begin-fast`.

## Pipeline

**REQUIRED SUB-SKILL:** Use `assay-begin-fast` for the base pipeline.

Run its **Phase 0 → Phase 4 and the ⛔ PRD review gate exactly as written.**

**Then, instead of going straight to tech-plan, insert Phase A below.**

### Phase A — Proposals (diagrams → PDFs)

Detailed steps: see `references/proposals.md`.

1. **Diagram** — Use `excalidraw`. Save to `docs/planning/{slug}/diagrams/*.excalidraw`.
2. **Export** — Use `excalidraw-to-svg`.
3. **Write two proposals** in `docs/planning/{slug}/proposals/`:
   - `<type>-<id>-technical-proposal.md` — architecture, components, data flow, risks, effort.
   - `<type>-<id>-non-technical-proposal.md` — problem, value, what changes, timeline, plain language.
4. **PDF** — Use `md-to-pdf`.

### ⛔ Approval gate — STOP

Present both PDFs. Wait for explicit approval before planning.

### Final phases — Plan & implement

Run `assay-begin-fast`'s **Phase 5 (tech-plan)** then **Phase 6 (implement, TDD via
agents team)**.

## Artifact layout

```
docs/planning/
├── _card/issue.md
├── {slug}/prd.md
├── {slug}/diagrams/*.excalidraw|.svg
├── {slug}/proposals/<type>-<id>-technical-proposal.{md,pdf}
├── {slug}/proposals/<type>-<id>-non-technical-proposal.{md,pdf}
└── {slug}/{aspect}/plan_*.md
```

## Common mistakes

| Mistake | Fix |
|---|---|
| Writing proposals before the PRD is approved | Phase A starts only after the first ⛔ gate |
| One proposal for both audiences | Always two |
| Embedding `.excalidraw` instead of `.svg` | PDFs embed the exported SVGs |
| Overstating what a verdict proves | `UNVERIFIED` is never drawn as `CLEAN`; `MALICIOUS` requires a reproduced behavior |
