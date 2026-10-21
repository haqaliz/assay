---
name: prd-interview
description: Conduct a collaborative product requirements interview between PM and engineering. Use when turning a brief or feature idea into a structured PRD and aspect-level specs through guided discovery and pressure-testing. Triggers on "prd interview", "requirements interview", "prd-interview".
tags:
  - documentation
  - planning
metadata:
  status: trial
---

# PRD Interview

Conduct a structured product requirements interview to turn a brief or feature idea into a complete PRD.
This is a collaborative exercise — the PM hat brings product context, the engineering hat brings technical reality.
Challenge assumptions. Pressure-test scope. Document what survives.

Do not create files until the Document phase.
If the tool supports a read-only or plan mode, switch to it now.

## Context

This skill is the first step in the brief-to-code pipeline (it's Phase 3 of `assay-begin-fast`).
Input is typically the gathered issue/brief dump at `docs/planning/_card/issue.md` plus the deep-dig understanding note.
Output is a structured PRD plus aspect-level specs that feed directly into `tech-plan`.

**Assay guardrail:** before documenting, sanity-check the work against `CLAUDE.md`. The moat is
the sandbox-observed behavior of a skill, diffed against what it declares, plus the compounding
findings corpus. It is **not** a static pattern scanner or a model's opinion of the skill's text
standing in for the verdict. If requirements drift toward a static-only signal deciding
`MALICIOUS`/`CLEAN`, flag it in the interview, not after.

## Discover & Challenge

Read the user's input — the issue dump, brief, or pasted requirements.
Read key files to understand the current architecture. Assay is **greenfield**: today that means
`docs/technical/CAPABILITY_ROADMAP.md` (A1..A10), `docs/technical/ARCHITECTURE.md`, and
`docs/ROADMAP.md`, plus `src/assay/` once it exists.
Ask if the user is aware of prior art (NVIDIA's SkillSpector, OWASP's Agentic Skills Top 10) —
offer to search if not.

Then pressure-test. Do not soften these.

- "What happens if we don't build this?"
- "Imagine this launched 6 months ago and failed. What went wrong?"
- "What are we choosing NOT to build if we build this?"

If the user has heard the challenge and wants to proceed, proceed.

Fill remaining gaps with focused questions, 2-3 at a time, grouped by topic:

- **Users & Problem**: Who has this problem? What's the cost of the status quo?
- **Success**: How will we measure it? Target numbers?
- **Scope**: What is explicitly out of scope?
- **Requirements**: Must-have vs. should-have vs. nice-to-have?
- **Technical Fit**: Which capability (`A1`..`A10`) and phase does this belong to, and are its
  dependencies built? Where does it sit in the ingest → sandbox → capture → diff → verdict →
  bundle pipeline?
- **Verdict impact**: Does this keep the **sandboxed, observed run** as the only thing that
  assigns `CLEAN`/`FLAGGED`/`MALICIOUS`? Does the floor (the four always-on finding classes)
  stay intact? What's the explicit `UNVERIFIED` path, with a named cause, when the sandbox can't
  run the skill or the dangerous path never triggers?

Skip what you can infer. Challenge vague answers. Flag technical pitfalls you read — don't wait
to be asked.

**Stop when** the problem is clear without guessing, success metrics are measurable, must-haves
have testable criteria, out-of-scope is explicit, and major technical risks are identified.

## Confirm

Summarize: the problem, proposed approach, scope, success criteria, risks, and unresolved
concerns. Ask the user to confirm before writing. Confirm the feature slug for the directory name
(e.g., `skill-ingest`, `sandbox-capture`). Do not name the slug `<type>-<id>`.

## Document

Omit sections that don't apply.

**Filename:** `prd.md`
**Location:** `docs/planning/{slug}/`.

```
docs/planning/{slug}/
├── prd.md                        ← this skill's output
├── {aspect}/                     ← one directory per aspect
│   ├── spec.md                   ← this skill's decomposition output
│   ├── plan_YYYYMMDD.md          ← tech-plan output
│   └── ...
└── ...
```

### PRD structure

- **Problem Statement**: What problem are we solving? For whom? Evidence it's real.
- **Goals & Success Metrics**: What does success look like? How will it be measured?
- **User Personas & Scenarios**: Who uses this and in what context? (Assay ICP: skill authors,
  registries like ClawHub/skills.sh, and enterprises deploying agents who need to know a skill
  does only what it says.)
- **Requirements**: Core features and behaviors, prioritized must/should/nice.
- **Technical Considerations**: Architecture fit, dependencies, integration points. Call out
  sandbox isolation and verdict impact explicitly, and name the capability (`A1`..`A10`).
- **Risks & Open Questions**: Reference the roadmap's `R1`..`R9` where one applies.
- **Out of Scope**: Explicitly excluded features or concerns.

Include when relevant: Finding Schema, Declared-Scope Grammar, Sandbox Config Contract, Bundle
Contract, Non-Functional Requirements.

After writing, surface open questions and unresolved risks. Then offer to continue into aspect decomposition.

## Aspect Decomposition Mode (same skill)

1. Propose aspect candidates (typically 2-8), each with a one-line boundary.
2. Confirm aspect names with the user (`kebab-case`).
3. For each confirmed aspect, write or update `docs/planning/{slug}/{aspect}/spec.md`.
4. Keep each spec focused and buildable by one engineer (or agent) at a time.

Each `spec.md`: problem slice and user outcome, in-scope requirements, out-of-scope boundaries,
acceptance criteria (testable — the repo is test-first), dependencies/sequencing, open
questions/risks specific to this aspect.

## Edge Cases

- **Update existing PRD**: Read the file, ask what changed, update in place.
- **Existing PRD, no aspect specs yet**: Run Aspect Decomposition Mode without re-running discovery.
- **User says "just write it"**: Write from what you have, flag gaps in Open Questions, still include at least one challenge question.
- **No brief exists**: Run full discovery from conversation.
- **Greenfield with no code to read**: Ground the technical section in the roadmap/design docs and say plainly that no implementation exists yet.
