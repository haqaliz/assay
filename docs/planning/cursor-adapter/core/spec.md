# Spec — `cursor-adapter` / `core` (A8)

## Problem slice & user outcome

A Cursor project rule (`.cursor/rules/*.mdc`) is ingested as a `Skill` with `Format.CURSOR`, its
body as instructions, and its file scope from `alwaysApply`/`globs`. `assay check` can run it, the
report says `format: cursor`, and a bundle of the rule verifies and replays. Claude/OpenClaw and the
existing bundle bytes are unchanged.

## In scope

- `Format.CURSOR`; `src/assay/ingest/cursor.py`; parser dispatch by suffix and content.
- `alwaysApply`/`globs` → `Scope.files`; tools/network `None`.
- Optional `SkillSource.format` for bundle replay; additive, no bundle schema bump.
- Ingest/bundle/CLI tests and docs; no A5/trace/corpus change.

## Out of scope

`.cursorrules` legacy, `AGENTS.md`, user/team rules, nested discovery; scripts/assets; MCP; directory
manifests; a bundle schema bump; Cursor's application policy.

## Parsing rules

- Input: a `.mdc` file with a YAML frontmatter block and a markdown body. No frontmatter → named
  `SkillParseError`.
- `name`: the file stem; `cursor-rule` if empty.
- `description`: frontmatter `description` (non-empty string) → else the first non-empty body line
  stripped → else the stem. A present non-string `description` → `INVALID_SCOPE`.
- `alwaysApply`: optional bool, default `false`; non-bool → `INVALID_SCOPE`.
- `globs`: optional string (comma-separated) or list of non-empty strings; trim; an empty entry or
  other type → `INVALID_SCOPE`.
- `scope`:
  - `tools=None`, `network=None`;
  - `files=("*",)` if `alwaysApply` is true (ignore globs);
  - else `files=tuple(globs)` if non-empty;
  - else `files=None`.
- `body`, `source_path`, `content_hash=sha256(raw)`, `format=CURSOR`, `requirements=()`.
- `parse_skill(path)`: `.mdc` suffix → cursor; otherwise the existing parser.
- `parse_skill_text(text, path=Path("SKILL.md"), *, format=None)`:
  - `CURSOR` → cursor parser;
  - `CLAUDE_CODE`/`OPENCLAW` → the existing parser (which detects OpenClaw);
  - `None` → if the frontmatter has `globs` or `alwaysApply` → cursor; else the existing parser.
  - Malformed frontmatter under `None` → the existing parser's named error.
- `looks_like_cursor(text) -> bool`: frontmatter has `globs` or `alwaysApply`; malformed → False.

## Bundle hint

- `SkillSource` gains `format: Format | None = None`.
- `to_payload()` includes `"format"` only when not `None`; `from_json` accepts
  `{content_hash, source}` or `{content_hash, source, format}` and validates the enum.
- `create_bundle` sets the format for a Cursor skill; it stays `None` for `CLAUDE_CODE`/`OPENCLAW`
  (their sources are self-describing), so existing bundle bytes are unchanged.
- `replay` passes the stored format to `parse_skill_text` when present; otherwise content detection.
- Bundle schema stays 2; the field is an additive extension. A Cursor rule whose source has only
  `description` still replays because the format is stored.
- `Bundle.__post_init__` hash checks are unchanged.

## Acceptance criteria

1. A `.mdc` with `alwaysApply: true` parses as `CURSOR`, `files=("*",)`, description from the body
   if absent, body/hash correct.
2. A `.mdc` with `globs: "src/**/*.ts, docs/**/*.md"` parses to those two file patterns; a list form
   also works; `alwaysApply` false.
3. A `.mdc` with only `description` parses with `files=None`.
4. A `.mdc` with no frontmatter, a non-string `description`, a non-bool `alwaysApply`, or bad
   `globs` (empty entry, non-string/list) raises `SkillParseError` with `INVALID_SCOPE`/frontmatter
   cause.
5. `parse_skill` on `.mdc` → CURSOR; on `SKILL.md` → the existing format; `parse_skill_text` detects
   the marker keys and accepts an explicit `format`.
6. A Cursor skill's bundle `to_payload()["skill"]["format"] == "cursor"`; a Claude/OpenClaw bundle
   has no `format` key and its canonical bytes are unchanged; `from_json` validates both shapes.
7. `build`/`verify` round trip a Cursor rule, including a description-only rule; `replay` uses the
   stored format and returns the stored assessment.
8. `assay check` on a `.mdc` with fakes reports `format: cursor`, `requirements: none`, and exits 0/1
   per the verdict; `bundle`/`verify` work on the saved trace.
9. A write inside the globs is not a finding; a write outside is `UNDECLARED_FILE` (FLAGGED); a rule
   with no findings is `UNVERIFIED/NO_DECLARED_SCOPE`, never `CLEAN`.
10. Claude and OpenClaw regression tests pass; the corpus is unchanged; `uv run pytest` is green and
    offline; no new dependency.

## Dependencies & sequencing

Ingest (`Format.CURSOR`, cursor parser, dispatch) → bundle optional format/replay → tests → docs.
Uses A1/A4/A5/A6; no trace/corpus/A5 change.

## Open questions / risks

- Most rules will be `UNVERIFIED` without findings; the format declares no tools/network.
- Globs vs Assay's `*`-crosses-`/` shortcut; differences are conservative but documented.
- The bundle hint is additive; old bundles still load; new Cursor bundles need current code.
- `.cursorrules`/`AGENTS.md`/team rules are out; a `.md` rule is ignored by Cursor and Assay treats
  it as a malformed `SKILL.md`.
- A rule's referenced scripts/assets are not attested; `SKILL.md`/`.mdc` only.
