# PRD — `skill-ingest` (A1: skill ingest and declared-scope extraction)

Status: draft for review. Date: 2026-10-28.
Pipeline position: A1 of `docs/technical/CAPABILITY_ROADMAP.md`. No dependencies; unblocks A3
(agent driver) and, through it, the Phase 0 gate in `docs/ROADMAP.md`.

## Problem statement

Assay's entire claim is *declared vs observed*. Today the "observed" half has a sandbox
(`src/assay/sandbox/`, A2, merged) and the "declared" half does not exist: nothing in the repo can
turn a skill into data. Without a typed `Skill` record there is nothing to diff a captured trace
against, and A5's four floor finding classes have no baseline that distinguishes "the skill never
claimed this" from "the skill claimed it does nothing here".

For whom: Assay itself (A3/A4/A5 consume the record), and secondarily a skill author running the
future `assay check` on their own `SKILL.md`.

Evidence it is real: `docs/ROADMAP.md` M0.1 and Phase 0's gate. The dogfood target (M0.3) is the
10 skills in `~/dev/at/plumb/.claude/skills/`.

## Goals and success metrics

| Goal | Metric (measurable in this slice) |
|---|---|
| A real skill becomes data | All 10 Plumb dogfood skills parse; `skill.name` equals the skill's directory name for all 10 |
| Malformed input is named, not a crash | Every refusal fixture raises `SkillParseError` with a machine-readable `cause`; zero tracebacks and zero uncaught exceptions |
| Absence is not emptiness | Separate tests assert `None` (undeclared) and empty (declared none) for tools, files and network, and that they differ in the record |
| Deterministic identity | `content_hash` is `sha256(raw bytes)`; equal bytes give equal hashes across runs |
| No execution at parse time | The parser never spawns a process, opens the network, or imports/evals skill content (asserted by the absence of such calls in `src/assay/ingest/`, reviewed at the security checkpoint) |

Not a goal: a verdict, a diff, a CLI, or any opinion about whether a skill is safe.

## Users and scenarios

1. **A4/A5 (the consumer)** — takes a `Skill`, compares `scope.files`/`scope.network`/`scope.tools`
   against captured events; needs `None` to mean "cannot judge" so it emits `UNVERIFIED/NO_DECLARED_SCOPE`
   rather than `CLEAN` or `MALICIOUS`.
2. **The dogfood run (M0.3)** — parses 10 real skills written by a human, none of which declare
   file or network scope, and must not refuse any of them.
3. **A skill author** — sees a precise refusal message naming the structural problem, not a
   traceback.

## Requirements

### Must have

1. **`Skill` record** (frozen): `name: str`, `description: str`, `scope: Scope`,
   `body: str`, `source_path: Path`, `content_hash: str`.
2. **`Scope`** with one field per dimension, each tri-state:
   - `tools: frozenset[str] | None`
   - `files: tuple[str, ...] | None`
   - `network: tuple[str, ...] | None`
   `None` = the skill declared nothing for that dimension. Empty = the skill declared that it does
   nothing for that dimension. These are different values and both round-trip.
3. **Sources of declared scope**:
   - `allowed-tools`: either a comma-separated string (as used by real skills:
     `Read, Grep, Glob, Bash, Write`) or a YAML list (`- Bash(git *)`, the form used by 8 of the
     official Anthropic plugins) → `tools`. An empty list is declared-none; an empty string or an
     empty/ non-string list member is `INVALID_SCOPE`.
   - `metadata.assay.files` (list of strings) → `files`.
   - `metadata.assay.network` (list of strings) → `network`.
   - Absent key → `None`. Present but empty list → `()`.
   No prose is ever interpreted: the markdown body is hashed and preserved, never parsed for
   intent (guardrail 1).
4. **Parser seam**: a `Parser` `Protocol` (`parse(path) -> Skill`) plus
   `ClaudeSkillParser`, mirroring `Sandbox` in `src/assay/sandbox/base.py`. Only `SKILL.md` is in
   scope; A8 adds formats behind the same seam.
5. **Named refusals**: `SkillParseError(cause, detail, path)` with `cause` from a closed set:
   `NOT_A_FILE`, `TOO_LARGE` (>1 MB), `NO_FRONTMATTER`, `INVALID_UTF8`, `INVALID_YAML`,
   `DUPLICATE_KEY`, `MISSING_NAME`, `MISSING_DESCRIPTION`, `INVALID_SCOPE`.
   Every refusal message names what to fix. Unsafe/invalid input never yields a partial record.
6. **Lenient on extras**: unknown frontmatter keys (`license`, `homepage`, `compatibility`,
   `version`, `model`, `effort`, `argument-hint`, `tags`, `metadata.*` other than `assay`) are
   ignored without error or warning. **De-facto-valid YAML**: a top-level `key: value` line whose
   plain scalar contains `": "` (e.g. `description: … Triggers: a, b`) is repaired by quoting that
   one value before parsing. Claude Code accepts these files (6 of 174 on the dev machine), and
   refusing them would lose real coverage. The repair is identity on already-quoted or
   indicator-led values and never invents nested structure.
7. **Deterministic hash**: `content_hash = sha256` of the file's raw bytes, lowercase hex.

### Should have

8. `parse_skill(path)` module-level convenience returning a `Skill`, so callers do not construct a
   parser for the default format.

### Nice to have (explicitly deferred)

- Name-vs-directory mismatch detection.
- CRLF frontmatter normalization beyond accepting it.
- Multiple skills per directory / nested discovery.
- Any structured extraction of body instructions.

## Technical considerations

- **Dependency**: YAML parsing needs a library. Recommendation: add `PyYAML` (BSD/MIT, ubiquitous,
  `yaml.safe_load`) as the project's first runtime dependency. Duplicate-key detection is not
  available from `safe_load`, so the parser uses a `SafeLoader` subclass whose
  `construct_mapping` raises on a repeated key — about ten lines. Hand-rolling YAML is rejected:
  quoting, block scalars and nested `metadata` already appear in the wild, and a wrong parse here
  is a silent scope error, which is exactly the class of bug this capability exists to prevent.
  `pyproject.toml` currently has zero runtime deps; this is a deliberate first one.
- **Layout** (matches A2's shape): `src/assay/ingest/records.py` (`Skill`, `Scope`,
  `SkillParseError`, `ParseCause`), `base.py` (`Parser` protocol), `claude.py`
  (`ClaudeSkillParser`, `parse_skill`), `__init__.py` (public surface only).
- **Frontmatter grammar accepted**: file starts with `---` on its own line, ends at the next `---`
  line; CRLF tolerated; a UTF-8 BOM before the first `---` tolerated. Everything after the closing
  delimiter is `body` (verbatim, no stripping beyond the delimiter lines).
- **Type strictness**: `name` and `description` must be non-empty strings (not lists, not null).
  `allowed-tools` must be a string; `metadata.assay.files`/`network` must be lists of non-empty
  strings. A wrong type is `INVALID_SCOPE`, not a coercion.
- **Path handling**: `source_path` is stored as given; the parser does not resolve symlinks or
  require the file to live in a skill directory. Non-regular file → `NOT_A_FILE`.
- **No execution**: no `subprocess`, no `socket`, no `eval`/`exec`/`importlib` in `ingest/`.
- **Tests are offline**: fixtures under `tests/fixtures/skills/`. The dogfood test reads
  `~/dev/at/plumb/.claude/skills/` and `pytest.skip`s when absent — real data, never a network call.
- **A5 mapping** (documented here, implemented later): `SkillParseError` → `UNVERIFIED/WONT_PARSE`;
  `scope.* is None` → A5 cannot judge that dimension (`UNVERIFIED/NO_DECLARED_SCOPE`), never `CLEAN`.

## Risks and open questions

| Risk | L/I | Mitigation |
|---|---|---|
| Concrete source of file/network scope is an Assay invention; no real skill uses `metadata.assay` yet, so A4/A5 will mostly see `None` (R1: unverifiable by default) | High/High | That is the honest outcome and the PRD makes it explicit: `None` → `UNVERIFIED`, not `CLEAN`. The dogfood run's value is measuring how often this happens |
| Empty `allowed-tools:` or empty list is treated as "declared none" when the author meant "unspecified" | Med/High | Only an explicit empty *list* for `files`/`network` means declared-none; an empty string for `allowed-tools` is a refusal (`INVALID_SCOPE`), because a bare key is structurally ambiguous |
| A YAML feature (anchors, multi-doc, block scalars) parses differently than the author expects, silently changing scope | Med/Med | `safe_load` + duplicate-key rejection + fixtures per construct; scope accepts only lists of strings, so an exotic type is a refusal |
| First runtime dependency (PyYAML) sets a precedent | Low/Low | One dependency, safety-loaded, no transitive surprise; pinned in `uv.lock` |
| Consumers start inferring scope from prose because `None` is common | Med/High | Out of scope here, and `CLAUDE.md` constraint 1 forbids it; A4's diff must render "undeclared" honestly |

Open question deferred to A3/A4 (not blocking): when a skill declares `allowed-tools` only, should
file/network `None` degrade the verdict to `UNVERIFIED` for every run, or should A4 diff only the
dimensions that were declared? Recommendation: the latter, with the unnamed dimensions listed as
coverage gaps in the record.

## Out of scope

- Any CLI, verdict, diff, trace, corpus, bundle or adapter (A3–A10).
- Inferring scope from the markdown body, description, or naming.
- Executing, importing, or resolving anything the skill references.
- Validating that declared paths/globs/hosts exist or are reachable.
- `metadata.assay` schema versioning (add a `version` key when a second consumer needs it).
- Linux, network, or model calls of any kind.

## Areas to strengthen before sharing (self-critique)

- 🟡 The `metadata.assay` namespace is a bet: if Claude Code ever rejects unknown keys, the
  declaration channel breaks. Verify tolerance once, record the result here.
- 🟡 Success is measured on 10 skills from one repo; a second source (installed skills under
  `~/.claude/skills/`) would strengthen the "extras are tolerated" claim.
- 🔴 No acceptance test yet proves that a *declared-but-exceeded* scope would be detectable — that
  is A4's job, and this PRD only guarantees the data shape is capable of expressing it.
- Question before greenlighting: **if every real skill returns `scope.files = None`, what does
  A1 actually buy the Phase 0 gate, and is `allowed-tools` alone a strong enough declared baseline
  for a first observed-vs-declared diff?**
