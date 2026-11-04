# PRD — `openclaw-adapter` (A8: first format adapter)

Status: approved 2026-11-05 (user approved the next milestone). Date: 2026-11-05.
Pipeline position: A8 / M2.4 first adapter. No A5 or trace change.

## Problem statement

ClawHub is the registry where the real attacks happened (ClawHavoc, 1,184+ malicious skills). OpenClaw
skills use the same `SKILL.md` shape as Claude Code but a different metadata block:
`metadata.openclaw` declares gating requirements (`requires.bins`, `anyBins`, `env`, `config`, `os`),
not file/network/tool scope. Assay currently parses the file as if it were Claude Code, ignores the
requirements, and can spend a run on a skill that declares a secret the sandbox will never provide,
then report `AGENT_FAILED` instead of the honest "this cannot run here". That is both wasted spend
and a misleading result.

For whom: a user checking a ClawHub skill before install; a skill author testing an OpenClaw skill;
the future registry gate.

## Goals and success metrics

| Goal | Metric |
|---|---|
| The format is recognised | A documented OpenClaw `SKILL.md` parses as `Format.OPENCLAW` with its declared requirements; a Claude Code file stays `Format.CLAUDE_CODE` |
| Unsatisfiable runs are refused before spend | `assay check` on a skill requiring `env`/`config`, a mismatched `os`, or a missing jail `bin` exits `1` with `UNVERIFIED/REQUIREMENTS_UNMET` and no model/sandbox call |
| Satisfiable skills still run | A skill with no requirements, or only met ones (`bin:ls`, matching `os`), runs through the normal pipeline |
| The report is honest | Human and JSON `check` output show `format` and `requirements`; the refusal detail names every unmet requirement |
| No collateral change | Claude Code output except the new fields, trace schema 2, bundles, corpus and A5 are unchanged; no new dependency |

## Users and scenarios

1. **User checking a ClawHub skill** — `assay check @owner/skill`; sees `format: openclaw`, the
   declared requirements, and either a run or `REQUIREMENTS_UNMET` with the exact missing item.
2. **Author** — sees which requirement blocks the sandbox and can decide whether to declare
   `metadata.assay` scope for a real verdict.
3. **Registry/CI** — parses the JSON `format`/`requirements` and the named refusal.

## Requirements

### Must have

1. **Format and requirements on `Skill`.** Add `Format(StrEnum)` with `CLAUDE_CODE = "claude-code"`
   and `OPENCLAW = "openclaw"`; `Skill.format: Format = Format.CLAUDE_CODE` and
   `Skill.requirements: tuple[str, ...] = ()`. Validate the format and the requirement prefixes
   (`bin:`, `any-bin:`, `env:`, `config:`, `os:`).
2. **OpenClaw detection and parsing.** In the existing `SKILL.md` parser:
   - if `metadata.openclaw` is absent, the skill is `CLAUDE_CODE` with no requirements;
   - if present, the skill is `OPENCLAW`; `metadata.openclaw` must be a mapping;
   - `metadata.openclaw.requires` is an optional mapping with:
     - `bins`: list of non-empty strings → one `bin:<name>` each, sorted;
     - `anyBins`: list of non-empty strings → one `any-bin:<name>,<name>` (sorted names);
     - `env`: list of non-empty strings → one `env:<NAME>` each, sorted;
     - `config`: list of non-empty strings → one `config:<path>` each, sorted;
   - `metadata.openclaw.os` is an optional list of non-empty strings → one `os:<value>,<value>`
     (sorted); `macos` is accepted as an alias for `darwin`;
   - unknown `metadata.openclaw` keys (`emoji`, `homepage`, `install`, `primaryEnv`, `skillKey`,
     `always`) are ignored; unknown `requires` keys are ignored for forward compatibility;
   - malformed blocks (non-mapping `openclaw`/`requires`, non-list or non-string entries) are a
     named `SkillParseError(INVALID_SCOPE)`.
3. **Requirement gate.** A pure `unmet_requirements(skill, *, which=shutil.which,
   platform=sys.platform, path=<jail PATH>) -> tuple[str, ...]`:
   - `env:` always unmet: the jail env is only `PATH`; no credentials or user env reach it;
   - `config:` always unmet: Assay has no OpenClaw gateway config;
   - `bin:` unmet when absent from the jail PATH;
   - `any-bin:` unmet when none is present;
   - `os:` unmet when the platform is not in the list (`macos`/`darwin` equivalence);
   - order preserves the `Skill.requirements` order.
4. **CLI gate.** `assay check` runs the requirement check after parse and before model/sandbox
   creation. Unmet → the existing refusal envelope (`schema`, `skill`, `verdict: unverified`,
   `cause: requirements-unmet`, `detail` listing the unmet requirements), exit `1`, no run, no
   trace, no spend.
5. **Report.** Human `check` adds `format: <value>` and `requirements: <comma list or none>`; JSON
   adds `format` and `requirements` to the `skill` object. The bundle/verify reports are unchanged.
   The exact check fixtures/tests are updated; the `schema` stays `1` (additive fields).
6. **Path source.** The jail `DEFAULT_PATH` moves to `sandbox/config.py` and is exported from
   `assay.sandbox`; `seatbelt.py` imports it (re-exported for existing callers). The requirement
   check uses it, so it cannot drift from the jail.
7. **Docs/status.** README supported formats, the `REQUIREMENTS_UNMET` behaviour and the new report
   fields; ARCHITECTURE ingest adapters and the gate; CAPABILITY_ROADMAP A8 (OpenClaw/ClawHub built;
   Cursor/MCP next); ROADMAP M2.4; CLAUDE.md status.
8. **Tests offline.** No network/model; parse fixtures use text; CLI uses the injected model/sandbox.
9. **No A5/trace/corpus change.** The trace stores the skill hash/name; the bundle re-parses the
   source; the corpus stays Claude. `Format`/`requirements` are derived from the source, not stored.

### Should have

10. The refusal detail is readable: `the sandbox cannot satisfy: env:GEMINI_API_KEY, os:linux`.
11. A test that `metadata.openclaw` with only ignored keys is still `OPENCLAW` with no requirements.
12. A test that a Claude skill with `metadata.assay` and no `openclaw` is unchanged.

### Nice to have (deferred)

`metadata.clawdbot` legacy support; JSON5-only frontmatter fallback; Cursor rules; MCP manifests;
the rest of the skill directory (scripts/assets); a ClawHub fetch command.

## Technical considerations

- **Same parser, new metadata.** The existing `SKILL.md` frontmatter/body parser is reused. Only the
  format detection and the `metadata.openclaw` extraction are new; no second YAML parser.
- **Requirements are declarations, not guarantees.** `requires.bins` is a host check in OpenClaw;
  Assay checks the jail PATH, which is narrower (`/usr/bin:/bin:/usr/sbin:/sbin`). A bin installed
  only in `/opt/homebrew` is honestly unavailable to the jail; the refusal says so.
- **`always: true` does not bypass the gate.** It is an OpenClaw load policy, not a secret or a
  sandbox capability. A skill that requires `GEMINI_API_KEY` still cannot use it in the jail.
- **`env`/`config` are always unmet.** The agent toolbox sets `JailConfig.env={}` and the child env
  is `{"PATH": DEFAULT_PATH}`; an OpenClaw skill gets no injected secret. Refusing before the run is
  the honest outcome; a run would end `UNVERIFIED/AGENT_FAILED` after spend.
- **`os` is the host platform.** The sandbox is Seatbelt-only (darwin); a Linux-only skill cannot
  run here. The refusal is `REQUIREMENTS_UNMET`, not `SANDBOX_UNAVAILABLE` (the sandbox exists; the
  skill's platform does not match).
- **Report schema.** Additive fields in `schema: 1`; existing consumers ignore extras. The
  byte-stability tests update once. The bundle/verify output stays stable.
- **Format detection.** `metadata.openclaw` wins; a file with both `openclaw` and `assay` metadata is
  an OpenClaw skill that also declares Assay scope (used by `assess`).
- **No new dependency.** PyYAML already parses the documented OpenClaw flow-style metadata; a
  JSON5-only file with single quotes/trailing commas may be refused by name. Document the limit.

## Risks and open questions

| Risk | L/I | Mitigation |
|---|---|---|
| Over-refusing a skill whose bin exists on the host but not in the jail | Med/Med | Refusal names the jail path; the sandbox cannot run it; honest |
| Under-refusing: `env` requirement but the tool doesn't need it | Low/Med | The declaration is the author's contract; refuse and let them remove it |
| `always` semantics misread | Low/Med | Document: load policy, not a capability; gate still applies |
| JSON5-only metadata fails | Med/Med | Named `INVALID_YAML`/`INVALID_SCOPE`; documented; fallback deferred |
| Report change breaks byte-stable consumers | Low/Med | Additive fields; one-time update; schema stays 1 |
| Format detection ambiguity | Low/Med | `metadata.openclaw` wins; both metadata blocks are valid |
| A ClawHub skill's scripts/assets are not attested | Med/High | The bundle covers `SKILL.md` only; document; directory manifest deferred |

Open questions (recommendations):

- **O1 — gate `bin` against the host or the jail?** [Jail; the jail is what runs it.]
- **O2 — `always: true` bypass?** [No; the secret/tool is still absent.]
- **O3 — `metadata.clawdbot`?** [Defer; the OpenClaw docs no longer read it.]
- **O4 — report fields in `schema: 1`?** [Yes, additive; bump only on a breaking shape change.]

Challenge: **does an adapter that mostly refuses runs add value?** Yes: it turns a guaranteed
`AGENT_FAILED` after spend into a named, pre-run refusal with the exact missing requirement, and it
makes the format visible instead of silently pretending it is Claude Code. The first adapter is
coverage plus honesty, not a new detector.

## Out of scope

- Cursor rules, MCP manifests, other formats.
- Running the OpenClaw runtime or its gateway config; injecting secrets.
- `metadata.clawdbot` legacy, JSON5-only fallback, fetching from ClawHub.
- A5 changes, trace schema 3, corpus changes, bundle schema changes.
- The rest of the skill directory (scripts/assets) in the hash.

## Areas to strengthen before sharing (self-critique)

- 🔴 **No scope declaration.** Most OpenClaw skills will still be `UNVERIFIED/NO_DECLARED_SCOPE`
  after a run because they declare no file/network/tool scope. The adapter does not fix that; it
  makes `metadata.assay` the optional way to get a real verdict. Say so.
- 🟡 **`bin` false refusals.** The jail PATH is narrow; a skill using a Homebrew binary is refused
  even if the user has it. That is correct for the jail but may surprise; the detail names the PATH.
- 🟡 **JSON5.** The documented example parses; the fallback is deferred. A malformed file gets a
  named refusal, not a wrong parse.
- 🟡 **Format detection is metadata-based.** A Claude skill with an `openclaw` block would be
  labelled OpenClaw; that is a fair reading of the file.
- Question before greenlighting: **should the first adapter gate on requirements at all, or only
  report them?** [Gate: a run that cannot satisfy a declared requirement is a guaranteed failure and
  spend; refusing is the honest default.]
