# Spec — `openclaw-adapter` / `core` (A8)

## Problem slice & user outcome

An OpenClaw/ClawHub `SKILL.md` is ingested as an OpenClaw skill, with its declared requirements
visible. A run the jail cannot satisfy is refused before any model or sandbox call with the exact
missing requirement; a satisfiable skill runs through the existing pipeline. Claude Code behavior is
unchanged.

## In scope

- `Format` enum, `Skill.format`, `Skill.requirements`.
- OpenClaw detection and `metadata.openclaw` parsing in the existing `SKILL.md` parser.
- Jail `DEFAULT_PATH` moved to `sandbox/config.py` and exported.
- `unmet_requirements` policy and the `check` pre-run refusal.
- Human/JSON `check` fields: `format`, `requirements`.
- Tests and docs; no A5/trace/corpus/bundle changes.

## Out of scope

Cursor rules, MCP manifests, other formats; the OpenClaw runtime/gateway; secret injection;
`metadata.clawdbot`; JSON5-only fallback; ClawHub fetching; the rest of the skill directory; A5;
trace schema 3; bundle schema changes.

## Data model

```python
class Format(StrEnum):
    CLAUDE_CODE = "claude-code"
    OPENCLAW = "openclaw"

@dataclass(frozen=True, slots=True)
class Skill:
    name: str
    description: str
    scope: Scope
    body: str
    source_path: Path
    content_hash: str
    format: Format = Format.CLAUDE_CODE
    requirements: tuple[str, ...] = ()
```

- `Skill.__post_init__` validates `format` is a `Format` and each requirement starts with
  `bin:`, `any-bin:`, `env:`, `config:` or `os:`, with a non-empty value; normalises to a tuple.
- `requirements` is derived from the frontmatter; it is not stored in the trace or bundle. The
  bundle replays by re-parsing the source.

## Parsing rules

- `metadata` absent, or no `openclaw` key → `CLAUDE_CODE`, `requirements=()`.
- `metadata.openclaw` present:
  - must be a mapping; `OPENCLAW`;
  - `requires` (optional) must be a mapping; each known field must be a list of non-empty strings:
    - `bins` → `bin:<name>` each, sorted;
    - `anyBins` → one `any-bin:<name>,<name>` (sorted, comma-joined);
    - `env` → `env:<NAME>` each, sorted;
    - `config` → `config:<path>` each, sorted;
  - `os` (optional) → one `os:<value>,<value>` (sorted, comma-joined); accept `macos` and `darwin`
    as the same platform at check time;
  - ignore `always`, `emoji`, `homepage`, `install`, `primaryEnv`, `skillKey`, and unknown
    `requires` keys;
  - a non-mapping `openclaw`/`requires`, or a non-list/non-string entry → `SkillParseError` with
    `INVALID_SCOPE` and a detail naming the field.
- `metadata.assay` scope parsing is unchanged; a file can carry both.

## Requirement gate

```python
def unmet_requirements(
    skill: Skill,
    *,
    which: Callable[[str, str], str | None] = shutil.which,
    platform: str = sys.platform,
    path: str = DEFAULT_PATH,
) -> tuple[str, ...]
```

- `env:<NAME>` → unmet (the jail provides no env beyond PATH).
- `config:<path>` → unmet (Assay has no OpenClaw gateway config).
- `bin:<name>` → unmet if `which(name, path)` is `None`.
- `any-bin:<a>,<b>` → unmet if none resolves.
- `os:<a>,<b>` → unmet if `platform` is not in the set; `macos` is treated as `darwin`.
- Returns in `Skill.requirements` order; `()` means satisfiable.

## CLI

- `_check` after `parse_skill`, before model/sandbox:
  - `unmet = unmet_requirements(skill)`;
  - non-empty → `refusal("requirements-unmet", "the sandbox cannot satisfy: " + ", ".join(unmet),
    path, args.json)` to stdout, exit `1`; no model, no sandbox, no trace.
- `render_human`: after the `skill:` line add `format: <format>` and
  `requirements: <comma list or none>`.
- `render_json`: `skill` object adds `"format"` and `"requirements"` (list).
- `check` schema stays `1`; the added fields are additive. Bundle/verify reports unchanged.
- `assay bundle`/`corpus` do not gate requirements; they operate on stored evidence.

## Acceptance criteria

1. `parse_skill_text` on the documented OpenClaw example returns `Format.OPENCLAW` and
   `("bin:uv", "env:GEMINI_API_KEY", "config:browser.enabled")`.
2. A Claude Code `SKILL.md` with no `metadata.openclaw` returns `Format.CLAUDE_CODE` and `()`.
3. `anyBins` and `os` parse as one comma-joined requirement each, sorted; `macos` is accepted.
4. Ignored metadata keys do not create requirements; an `openclaw` block with only ignored keys is
   still `OPENCLAW`.
5. Malformed `openclaw`/`requires`/entries raise `SkillParseError` with `INVALID_SCOPE`; the detail
   names the field.
6. `unmet_requirements` (unit table): env/config always; missing/present bin; any-bin all/one/none;
   os match/mismatch/`macos`; order preserved.
7. `check` on an OpenClaw skill with `env`/`config`/mismatched `os`/missing bin exits `1`, prints
   `UNVERIFIED` + `REQUIREMENTS_UNMET` (+ the JSON envelope), and calls neither the model nor the
   sandbox (assert with fakes that would fail if called).
8. `check` on an OpenClaw skill with no requirements or met ones (`bin:ls`, `os:darwin`) runs the
   normal pipeline; the human/JSON report shows `format` and `requirements`.
9. Claude Code `check` output changes only by the two new report fields; the exact-byte tests update
   once; `bundle`/`verify`/`corpus` outputs are unchanged.
10. `DEFAULT_PATH` is defined once in `sandbox/config.py`, exported from `assay.sandbox`, used by
    `seatbelt.py` and the gate; the seatbelt tests that import it still work.
11. `uv run pytest` green and offline; no new dependency; no A5/trace/corpus change.

## Dependencies & sequencing

Ingest (`Format`, requirements) → sandbox `DEFAULT_PATH` export → requirement gate + CLI/report →
tests → docs. Uses A1 (`Skill`/parser), A2 (jail PATH), A5 (unchanged), A6 (bundle replay re-parses).
No corpus regeneration.

## Open questions / risks

- Jail PATH is narrower than the host; a Homebrew-only bin is honestly refused.
- `always: true` does not bypass the gate; the secret/capability is still absent.
- JSON5-only frontmatter may fail by name; the documented flow-style example parses.
- Most OpenClaw skills declare no file/network/tool scope and will be `UNVERIFIED/NO_DECLARED_SCOPE`
  after a run; `metadata.assay` remains the optional declaration for a real verdict.
- The rest of the skill directory is not attested; `SKILL.md` only.
