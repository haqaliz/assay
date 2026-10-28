# Spec — `skill-ingest` (A1, whole capability)

## Problem slice & user outcome

Given a path to a Claude Code `SKILL.md`, return a frozen `Skill` record whose `Scope` states, per
dimension, whether the skill declared something, declared nothing, or is silent — or raise a
`SkillParseError` naming the reason. Nothing in the file is executed, imported, or interpreted.

Outcome: A4/A5 have a declared baseline to diff against, and silence (`None`) is distinguishable
from denial of scope (`()`), so an undeclared dimension can map to `UNVERIFIED` instead of passing
as `CLEAN`.

## In scope

- `Skill`, `Scope` (frozen, validated), `ParseCause`, `SkillParseError`.
- `Parser` protocol + `ClaudeSkillParser` + `parse_skill(path)`.
- Frontmatter split (BOM, CRLF, first `---` at byte 0, closing `---`); body preserved verbatim.
- `allowed-tools` → `tools`; `metadata.assay.files` / `.network` → `files` / `network`.
- Duplicate-key rejection; unknown-key tolerance.
- `content_hash` = sha256 of raw file bytes.
- Offline fixtures + dogfood parsing of real skills when present.

## Out of scope

Any CLI, verdict, diff, trace, corpus, bundle, adapter, discovery, name-vs-directory check,
prose interpretation, scope validation against the filesystem or network.

## Acceptance criteria

1. A minimal real-shaped skill parses: `name`, `description`, body, `content_hash` correct.
2. `allowed-tools: "Read, Grep, Glob, Bash, Write"` → `tools == frozenset({...})`; the YAML list
   form (`allowed-tools:\n  - Read\n  - Bash(git *)`) yields the same `frozenset`; `[]` is
   declared-none.
3. Absent `allowed-tools` → `tools is None`; `allowed-tools: ""` → `SkillParseError(INVALID_SCOPE)`.
4. Absent `metadata.assay` → `files is None and network is None`.
5. `metadata.assay: {files: [], network: []}` → `files == () and network == ()`, and these are
   distinct from `None` (asserted on the same record shape).
6. `metadata.assay.files: ["./out/**", "report.md"]` → `files == ("./out/**", "report.md")`.
7. Refusals, each with its `cause`: missing file / directory → `NOT_A_FILE`; >1 MB → `TOO_LARGE`;
   invalid UTF-8 → `INVALID_UTF8`; no leading `---` or no closing `---` → `NO_FRONTMATTER`;
   unparseable YAML → `INVALID_YAML`; duplicate key → `DUPLICATE_KEY`; missing or non-string `name`
   → `MISSING_NAME`; missing or non-string `description` → `MISSING_DESCRIPTION`;
   wrong-typed `allowed-tools` / `metadata` / `assay` / scope lists → `INVALID_SCOPE`.
8. Unknown keys (`license`, `homepage`, `compatibility`, `version`, `model`, `effort`,
   `argument-hint`, `tags`, `metadata.owner`) are ignored without error.
9. CRLF file parses identically to its LF twin.
10. `content_hash` is stable across two parses of the same bytes and differs when a byte changes.
11. A top-level plain scalar containing `": "` (invalid strict YAML, accepted by Claude Code) is
    repaired and parsed; the stored description keeps the literal text.
12. Dogfood (skipped when absent): all `~/dev/at/plumb/.claude/skills/*/SKILL.md` parse and
    `skill.name == directory name`; every skill under `~/.claude/skills/` and `~/.claude/plugins/`
    either parses or raises `SkillParseError` — never another exception type.

## Dependencies & sequencing

None. Consumes the house conventions established by A2 (`src/assay/sandbox/`): frozen dataclasses
validated in `__post_init__`, a `Protocol` seam, named failures, offline tests. Adds PyYAML as the
first runtime dependency (approved at the PRD gate).

## Open questions / risks

- `metadata.assay` is an Assay dialect with no real usage yet; unverified whether Claude Code
  tolerates the key. If it does not, the channel moves to a sibling file and only A1 changes.
- `metadata` in the wild is a mapping; a non-mapping `metadata` is treated as `INVALID_SCOPE`
  because it blocks scope reading.
