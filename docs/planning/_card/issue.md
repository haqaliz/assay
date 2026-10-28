# feat skill-ingest — A1: Skill ingest and declared-scope extraction

## Brief

> Build A1 — parse a Claude Code `SKILL.md` into a typed, frozen `Skill` record (name,
> description, declared tools, declared file scope, declared network scope), with malformed input
> as a *named refusal* (a typed error mapping to `UNVERIFIED/WONT_PARSE`), never a traceback and
> never silent defaults. Parsing is pure data handling: nothing in the skill is executed at parse
> time (guardrail 1). Grep-check real fixtures: the 10 skills in `~/dev/at/plumb/.claude/skills/`
> declare only `name`/`description`/`arguments`, so the record MUST distinguish "no scope
> declared" from "declared empty scope" — assert both cases, since A4/A5 depend on it (R2: a false
> `MALICIOUS` on a legitimate skill). Follow the house shape: `src/assay/ingest/` with a `Parser`
> seam like `src/assay/sandbox/base.py`, frozen dataclasses with `__post_init__` validation like
> `src/assay/sandbox/config.py`, deterministic hash for later bundling, tests offline in `tests/`.
> Acceptance: a real `SKILL.md` parses into the record; malformed/frontmatter-less input is a
> named refusal; both scope-absent and scope-empty round-trip distinctly; no CLI yet (that's
> M1.4) and no diff/verdict logic.

Source: chosen by `assay-next` as the highest-leverage next capability (A1, no dependencies, on the
Phase 0 gate path and M0.3 dogfood). No GitHub issue exists (`gh issue view 1` is the merged A2
card).

## Context carried from the pick

- `docs/technical/CAPABILITY_ROADMAP.md` A1: *"Parse a skill (Claude Code `SKILL.md` first) into a
  typed record: name, description, declared tools, declared file and network scope. Malformed
  input is a named refusal."* Depends on: none. Guardrail: *"A skill is data, never executed at
  parse time."*
- `docs/ROADMAP.md` M0.1: *"A `SKILL.md` parses into a typed `Skill` record with declared scope;
  malformed input is a named refusal"*. Phase 0 gate: one real skill run end to end with an
  observed behavior that differs from a declared one. M0.3: dogfood the skills in
  `~/dev/at/plumb/.claude/skills/`.
- `docs/technical/ARCHITECTURE.md`: pipeline is ingest → sandbox → driver → capture/diff →
  verdict → bundle; layout puts A1 in `src/assay/ingest/`; tests run offline.
- `CLAUDE.md` constraint 1: execution decides, never a static scan; constraint 4: `UNVERIFIED`
  causes include `WONT_PARSE`; R1/R2 in `docs/ROADMAP.md`: a skill with no observable bad behavior
  is `UNVERIFIED`, never `CLEAN`, and a false `MALICIOUS` on a legitimate skill is High impact.
- Real fixture shape (`~/dev/at/plumb/.claude/skills/plumb-next/SKILL.md`): YAML frontmatter with
  `name`, `description`, `arguments` only. No scope keys are declared by any real skill today.
