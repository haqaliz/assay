---
name: prd-generator
description: Generate, critique, and refine PRDs, spec files, and roadmaps for initiative-level planning. Use to pressure-test and strengthen a PRD before planning. Triggers on "prd-generator", "prd generator".
tags:
  - documentation
  - planning
metadata:
  status: trial
---

# PRD Generator

## Philosophy

This skill is framework-neutral. When coaching, always present multiple applicable frameworks, explain tradeoffs between them, and let the user choose.

Default to **critical feedback over validation**. Always identify gaps, challenge assumptions, and ask hard questions — then offer constructive paths forward.

## Context

This skill supports planning at initiative scope. In the `assay-begin-fast` pipeline it is
Phase 4: refine and self-critique the `prd.md` that `prd-interview` produced, then surface the
gaps before the review gate.

For collaborative PRD creation from a brief, use the `prd-interview` skill.

## Capabilities

| Capability | Trigger Phrases | Output |
|-----------|----------------|--------|
| **Critique PRDs/Specs** | "review my PRD", "critique this spec", "what's missing" | Structured critique with severity ratings |
| **Generate PRDs** | "write a PRD for", "create a spec", "draft requirements" | Complete PRD document (markdown) |
| **Coach on Frameworks** | "how should I prioritize", "explain RICE", "opportunity sizing" | Framework comparison with worked examples |
| **Review Roadmaps** | "review my roadmap", "prioritization feedback", "sequencing" | Prioritization analysis with alternative orderings |

## Workflow 1: Critique PRDs/Specs

### Step 1 — Read the full document

Never critique based on partial reads.

### Step 2 — Score across dimensions

Rate each dimension as 🔴 Critical Gap, 🟡 Needs Work, or 🟢 Strong:

1. **Problem Definition** — Is the problem clearly stated? Evidence it's real?
2. **User Understanding** — Are target users defined and validated?
3. **Success Metrics** — Measurable, time-bound, tied to outcomes?
4. **Scope Clarity** — In/out of scope explicit? Hidden assumptions?
5. **Edge Cases & Risks** — Failure modes, dependencies, technical risks?
6. **Stakeholder Alignment** — Who approves, builds, is impacted?
7. **Feasibility Signal** — Engineering reality considered?
8. **Verdict Honesty & Sandbox Discipline** *(Assay-specific)* — Does the work keep the
   sandboxed, observed run as the only thing that assigns `CLEAN`/`FLAGGED`/`MALICIOUS`? Does
   the always-on floor stay intact? Is `MALICIOUS` reserved for a captured, reproduced behavior,
   never an inference from a skill's text? Is `UNVERIFIED` honestly used when the sandbox can't
   run the skill or the dangerous path never fires?

### Step 3 — Identify the top 3 gaps

### Step 4 — Ask the hard question

End every critique with ONE pointed question the author probably hasn't considered.

## Workflow 2: Generate PRDs

### Step 1 — Gather inputs

### Step 2 — Select PRD depth

| Template | Best For | Depth |
|----------|----------|-------|
| **Lightweight Brief** | Small features, experiments | 1-2 pages |
| **Standard PRD** | Mid-size features | 3-5 pages |
| **Full Spec** | Large initiatives | 5-10+ pages |

Problem Statement → Goals & Success Metrics → Users & Scenarios → Requirements → Technical
Considerations (incl. sandbox/verdict impact) → Risks & Mitigations → Out of Scope.

### Step 3 — Generate the PRD

Always include: explicit assumptions, open questions, a "Risks & Mitigations" section. Reference
the roadmap's `R1`..`R9` and the capability (`A1`..`A10`) the work belongs to.

### Step 4 — Self-critique

Run Workflow 1 against your own output. Flag 🔴/🟡 areas as "Areas to strengthen before sharing."

## Workflow 3: Coach on Frameworks

Prioritization: RICE, ICE, MoSCoW, Kano, Weighted Scoring, Cost of Delay / WSJF.
Problem discovery: Jobs-to-Be-Done, Opportunity Solution Trees, Double Diamond.
Strategy: Porter's Five Forces, Blue Ocean, Wardley Mapping.
Sizing: TAM/SAM/SOM, Fermi estimation.

## Workflow 4: Review Roadmaps & Prioritization

| Approach | Optimizes For | Tradeoff |
|----------|--------------|----------|
| **Impact-first** | Maximum outcome per unit time | May defer foundational work |
| **De-risk first** | Reduce uncertainty early | Slower visible progress |
| **Quick wins first** | Momentum | May delay strategic bets |
| **Dependencies-first** | Unblock parallel work | Front-loads less exciting work |

## Visual-First Preview

```
PRD: {slug}
├─ Problem ........... {one line}
├─ Goals/Metrics ..... {one line}
├─ Users/Scenarios ... {one line}
├─ Requirements ...... must:{n}  should:{n}  nice:{n}
├─ Technical ......... {sandbox/verdict impact in a phrase}
├─ Risks ............. {top risk}
└─ Out of scope ...... {one line}
```

## Output Format

- Default document format is **markdown** into `docs/planning/{slug}/`.
- Use tables for comparisons and severity indicators (🔴🟡🟢).

## Anti-Patterns (Never Do These)

1. Never just validate.
2. Never prescribe a single framework.
3. Never generate a PRD without flagging its own gaps.
4. Never give generic advice.
5. Never skip the hard question.
6. **Never wave through a static-only verdict dressed as verification** — if a PRD's verdict
   rests on a pattern match or a model's reading of the skill's text rather than an observed
   sandbox run, or lets either assign `MALICIOUS`/`CLEAN`, or renders `UNVERIFIED` as `CLEAN`,
   that's a 🔴 regardless of how good the rest is.
