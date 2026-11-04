# PRD — `cursor-adapter` (A8: second format adapter)

Status: approved 2026-11-05 (user asked for the next milestone). Date: 2026-11-05.
Pipeline position: A8 / M2.4, after OpenClaw/ClawHub. No A5 or trace change.

## Problem statement

Cursor project rules are system-level instructions scoped to files by globs. They are a real,
widely used skill-like format, and Assay cannot read them: `assay check .cursor/rules/foo.mdc`
would try to parse it as a `SKILL.md` and fail (no `name`). That is a coverage gap for a format
whose file scope is declared and observable: a rule that writes outside its globs is exactly the
kind of undeclared behavior Assay exists to catch.

For whom: a team checking a shared Cursor rule; a rule author; a future registry/CI gate.

## Goals and success metrics

| Goal | Metric |
|---|---|
| `.mdc` is a first-class input | `assay check`, `bundle` and `verify` accept a Cursor project rule and report `format: cursor` |
| The declared scope is used | `alwaysApply: true` → all files; `globs` → the file patterns; a write outside them is `FLAGGED` (`UNDECLARED_FILE`) |
| No false CLEAN | A rule with no findings stays `UNVERIFIED/NO_DECLARED_SCOPE` because tools/network are undeclared; `CLEAN` is not emitted |
| Bundles replay | A Cursor rule bundles and `verify` replays it, including a rule whose source has only `description` (no globs/alwaysApply) |
| No collateral change | Claude/OpenClaw behavior, trace schema 2, corpus, A5 and existing bundle bytes are unchanged; no new dependency |

## Users and scenarios

1. **Team checking a shared rule** — `assay check .cursor/rules/react.mdc`; sees `format: cursor`,
   the globs as requirements/scope, and a verdict.
2. **Author** — a rule that writes outside its globs is flagged with the file evidence.
3. **Registry/CI** — bundles and replays the rule as an attestation.

## Requirements

### Must have

1. **Format.** Add `Format.CURSOR = "cursor"`. The Cursor parser returns
   `Skill(format=Format.CURSOR, requirements=())`.
2. **Parser (`src/assay/ingest/cursor.py`).**
   - `parse_cursor_rule(path)` and `parse_cursor_text(text, path=Path("rule.mdc"))`.
   - YAML frontmatter required (`---` block); malformed is a named `SkillParseError`.
   - `description`: frontmatter `description` if a non-empty string; else the first non-empty body
     line (stripped); else the file stem. If present and not a string → `INVALID_SCOPE`.
   - `name`: the file stem (non-empty; fall back to `cursor-rule`).
   - `alwaysApply`: optional bool (default `false`); non-bool → `INVALID_SCOPE`.
   - `globs`: optional string (comma-separated) or list of non-empty strings; trim; empty entries or
     other types → `INVALID_SCOPE`.
   - `scope.files`:
     - `alwaysApply: true` → `("*",)`;
     - else `globs` present and non-empty → the tuple of patterns;
     - else `None` (agent-selected/manual rule; no file scope).
   - `scope.tools`/`scope.network` → `None`.
   - `body` = the markdown after the frontmatter; `content_hash` = sha256 of the file bytes.
   - `parse_skill(path)` dispatches `.mdc` → cursor, otherwise the existing parser; `parse_skill_text`
     takes an optional `format: Format | None`; without it, content detection uses the
     `globs`/`alwaysApply` marker keys, otherwise the `SKILL.md` parser.
   - `.cursorrules` (legacy, no frontmatter), `AGENTS.md`, user/team rules are out of scope.
3. **Bundle format hint.** `SkillSource` gains an optional `format: Format | None`. `create_bundle`
   sets it for Cursor sources (a `.mdc` is not self-describing enough); `SkillSource.to_payload`
   emits `"format"` only when set, so existing Claude/OpenClaw bundle bytes are unchanged and
   schema-2 bundles without the field still load. `Bundle.from_json` accepts `skill` with or without
   `format` and validates it. `replay` uses the stored format when present, otherwise the content
   detection. The bundle schema stays 2; document the compatible extension.
4. **CLI.** No new flags. `check`/`bundle` on a `.mdc` path work through `parse_skill`; the report
   already carries `format`/`requirements` from the OpenClaw slice. A directory path still appends
   `SKILL.md`; a user points at the `.mdc` file. A Cursor rule's `requirements` is `()`.
5. **Tests.** Ingest table (always/globs/string/list/description fallback/malformed); `parse_skill`
   by suffix and `parse_skill_text` detection; bundle round trip with the format hint; a
   description-only rule bundles/replays; CLI check/bundle/verify of a `.mdc` with fakes; Claude and
   OpenClaw regression; exact report bytes.
6. **Docs/status.** README formats, scope semantics, limits; ARCHITECTURE ingest adapters, globs →
   files, bundle format hint; CAPABILITY_ROADMAP A8 (OpenClaw + Cursor built; MCP next); ROADMAP
   M2.4; CLAUDE.md.
7. **No A5/trace/corpus change; no new dependency.**

### Should have

8. A test that a write outside `globs` is `FLAGGED` and a write inside is not a finding.
9. A test that `alwaysApply: true` maps to `("*",)` and ignores globs.
10. The report shows `format: cursor` and `requirements: none`.

### Nice to have (deferred)

`.cursorrules` legacy; `AGENTS.md`; user/team rules; scripts referenced by a rule; nested
`.cursor/rules` discovery; MCP.

## Technical considerations

- **Why globs → files.** A Cursor rule declares which files it applies to. `Scope.files` is the
  closest existing dimension; a write outside the globs is `UNDECLARED_FILE` (REVIEW) and a sensitive
  absolute write can be `HIGH`. Tools/network are undeclared, so the verdict is `UNVERIFIED` when
  there are no findings; that is honest.
- **`alwaysApply` is a scope declaration, not a safety claim.** `("*",)` means the rule may apply to
  all files, not that it is safe.
- **Why the bundle needs a format hint.** A `SKILL.md` is self-describing (`name`/`description` vs
  `metadata.openclaw`); a `.mdc` with only `description` has no marker key. Storing the format in
  `SkillSource` makes replay deterministic without bumping the bundle schema; the field is omitted
  for the existing formats, so their canonical bytes do not change.
- **Parser reuse.** The Cursor parser uses the existing frontmatter/read helpers; no second YAML
  parser. `globs` string splitting is Cursor's documented comma form.
- **Name/description.** A rule has no `name`; the file stem is the identity. A rule with no
  `description` still has a body; the first non-empty line is a useful fallback for `task_for`, which
  needs a description.
- **No new dependency.**

## Risks and open questions

| Risk | L/I | Mitigation |
|---|---|---|
| A rule with no tools/network scope never reaches `CLEAN` | High/Med | Honest: the format does not declare them; docs say so; `metadata.assay` is not part of Cursor |
| Globs vs Assay's `*`-crosses-`/` shortcut | Med/Med | The shortcut is conservative for findings; document; `src`/`**` patterns work |
| The bundle format hint is a schema-2 extension | Low/Med | Optional, omitted for existing formats; old bundles still load; docs |
| A `.mdc` with only `description` is ambiguous to content detection | Med/Med | The bundle stores the format; file suffix `.mdc` at check time; tests |
| `.cursorrules`/`AGENTS.md` users expect support | Med/Med | Explicitly out of scope; a named refusal (parsed as SKILL.md) is not ideal; document |
| A rule's referenced scripts/assets are not attested | Med/High | `SKILL.md`/`.mdc` only; directory manifest deferred |

Open questions (recommendations):

- **O1 — `alwaysApply` + globs both present?** [Always wins; `("*",)`; Cursor ignores globs when true.]
- **O2 — description fallback?** [First non-empty body line, then the stem; keep `task_for` usable.]
- **O3 — bundle format always?** [Only for Cursor now; omit for `SKILL.md` to keep old bytes stable.]
- **O4 — `.cursorrules`/AGENTS.md?** [Defer; separate format decisions.]

Challenge: **is a Cursor rule a “skill” Assay should run?** It is instructions, not a tool-using
skill. Assay can still observe what the model does under those instructions and diff file access
against the globs; that is a real check. It cannot prove the rule's referenced scripts are safe;
the docs must say so.

## Out of scope

- `.cursorrules` legacy, `AGENTS.md`, user/team rules, nested rule discovery.
- Scripts/assets referenced by a rule; directory manifests.
- MCP manifests.
- A5/trace/corpus/bundle schema changes (the format hint is additive, no bump).
- Cursor's actual application policy (agent-selected vs manual); Assay runs the rule as instructions
  for one task.

## Areas to strengthen before sharing (self-critique)

- 🔴 **Most Cursor rules will be `UNVERIFIED`.** Without tools/network, a no-finding run cannot be
  `CLEAN`; the adapter's value is file-scope findings and coverage. Say it.
- 🟡 **Glob semantics.** Cursor's `*`/`**` and Assay's fnmatch shortcut differ at the edges; the
  shortcut is conservative, but a pattern may match more than Cursor would. Document.
- 🟡 **Description fallback is a heuristic.** A rule whose body starts with a heading gets a
  heading as its description; acceptable for `task_for`, not a semantic field.
- 🟡 **Only project rules.** User/team rules are not files we can read; `AGENTS.md` is a different
  format.
- Question before greenlighting: **should a Cursor rule with no globs and `alwaysApply: false` be
  treated as `files=None` or refused?** [`files=None`: it is a valid agent-selected/manual rule;
  the verdict is `UNVERIFIED` without findings, not a refusal.]
