# feat cursor-adapter — A8 second format adapter

## Brief

Add Cursor project-rule support: `.cursor/rules/*.mdc` files with YAML frontmatter (`description`,
`globs`, `alwaysApply`). Parse the rule into a `Skill` with `Format.CURSOR`, the body as
instructions, and `scope.files` from `alwaysApply` (`("*",)`) or `globs` (comma-separated string or
list); `tools`/`network` stay undeclared. `assay check`, `bundle` and `verify` accept a `.mdc` file;
the report shows `format: cursor`. Because a `.mdc` is not a `SKILL.md`, the bundle carries an
optional `skill.format` so replay uses the Cursor parser even when the source has no marker keys.
A rule that writes outside its globs is `FLAGGED`; a rule with no findings stays
`UNVERIFIED/NO_DECLARED_SCOPE` because it declares no tools/network. No A5, trace or corpus change;
no new dependency.

Source: `docs/technical/CAPABILITY_ROADMAP.md` A8 / `docs/ROADMAP.md` M2.4 (Cursor rules next after
OpenClaw). Format grounded in `https://cursor.com/docs/context/rules` (2026-11-05): `.mdc` in
`.cursor/rules`, frontmatter `description`/`globs`/`alwaysApply`, globs comma-separated; `alwaysApply`
true ignores globs/description; `.md` is ignored; `AGENTS.md` and user/team rules are not project
rules.

## Context carried from the pick

- OpenClaw/ClawHub shipped (PR #13); Cursor is the next adapter in the documented order.
- `Skill` has `format` and `requirements`; the parser dispatch is content/extension based.
- The bundle stores `skill.source` and replays it; a `.mdc` source needs a parser hint because it is
  not a `SKILL.md`.
- The jail/agent driver runs the rule as instructions; file events are captured and diffed against
  the globs. Tools/network are not declared by the format.
- Constraints: no A5/trace/corpus change; `UNVERIFIED` is not a pass; no new dependency.
