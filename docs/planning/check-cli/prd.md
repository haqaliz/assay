# PRD — `check-cli` (M1.4: `assay check <skill>`)

Status: draft for review. Date: 2026-10-31.
Pipeline position: Phase 1 milestone M1.4 (the `assay` product surface over A1–A5). No new detection
logic; this is the command that runs the pipeline and reports it.

## Problem statement

Every capability now exists as an importable library, and none of it is reachable by a user. The
Phase 0 gate itself ("one real skill run end to end") is a Python snippet today. There is no
`assay` command, no exit contract, and no stable machine-readable output that CI or a registry could
consume.

For whom: the maintainer running the first keyed check, a skill author checking their own skill, and
the future GitHub Action / registry gate.

## Goals and success metrics

| Goal | Metric |
|---|---|
| One command runs the whole pipeline | `assay check <skill>` parses, runs, captures, stores the trace, assesses, prints, and exits |
| Exit contract | `0` only on `CLEAN`; `1` on `FLAGGED`/`MALICIOUS`/`UNVERIFIED` (including a sandbox that cannot start); `2` on usage/config error |
| Machine-readable and stable | `--json` emits one canonical line; two identical runs (same fake model and fixture) produce byte-identical output |
| A record survives | The trace is written to `<out>/<sha256>.json` (default `./.assay/traces`) and its path is printed |
| Nothing is spent blind | `--max-cost`, `--model`, and both prices are required (flags or env); the cap and model are shown before the run |
| No traceback ever | Any handled failure prints one line naming the cause; an unexpected error exits `2` with its type and message |
| BYOK only | The key is read from `ANTHROPIC_API_KEY`, never printed, never written into the trace or jail env |

Not a goal: a bundle, a corpus, adapters, `assay install`, watch mode, a progress UI, or new
detection rules.

## Users and scenarios

1. **Maintainer running the gate** — `assay check ~/dev/at/plumb/.claude/skills/plumb-next --model … --input-price … --output-price … --max-cost 0.50`, then reads the trace.
2. **Skill author in CI** — `--json`, parse the verdict, use the exit code.
3. **Reviewer** — reads the human report and opens the trace path.

## Requirements

### Must have

1. **Console script**: `[project.scripts] assay = "assay.cli:main"`; `main(argv=None) -> int`.
   `assay check <skill>` is the only command; `--help` works; unknown command → exit 2.
2. **Options**:
   - `--strictness {baseline,standard,strict}` (default `standard`)
   - `--max-cost USD` (required, positive)
   - `--model NAME` (required; env `ASSAY_MODEL`)
   - `--input-price USD_PER_MTOK`, `--output-price USD_PER_MTOK` (required; env
     `ASSAY_INPUT_PRICE`, `ASSAY_OUTPUT_PRICE`)
   - `--max-steps` (default 20), `--max-actions` (default 40), `--max-wall-seconds` (default 300)
   - `--out DIR` (default `./.assay/traces`), `--json`, `--keep-run-root`
3. **Flow**: parse with `parse_skill`; build `AnthropicModel.from_env`; create a private run root;
   `task_for`; `drive`; `capture`; `TraceStore(out).save`; `assess` with
   `StrictnessPolicy(level=…)`; print; clean the run root unless `--keep-run-root`.
4. **Parse refusal**: no trace exists, so no `Assessment`. Print (human or JSON) an envelope with
   `verdict: UNVERIFIED`, `cause: WONT_PARSE`, the skill path and the `SkillParseError` detail;
   exit 1.
5. **Missing key / missing model settings / bad numbers**: exit 2 with one line naming what is
   missing; no run, no trace.
6. **Sandbox unavailable** (non-macOS or missing `sandbox-exec`): exit 1 with
   `UNVERIFIED` / `SANDBOX_UNAVAILABLE`; nothing ran.
7. **A3 stop causes**: `cost-capped` → `UNVERIFIED/COST_CAPPED`; other causes →
   `UNVERIFIED/AGENT_FAILED`. The trace is still captured and saved when one exists, and findings
   from what ran before the stop are kept (an early stop must not hide a dangerous action).
8. **Human output**: skill name and short hash, verdict, cause (or `-`), strictness and whether the
   run is blocked, one line per finding with class/severity/target/reason, the trace path, and the
   cost with token counts.
9. **JSON output**: one canonical line (`sort_keys`, compact separators, UTF-8, trailing newline)
   with `schema`, `skill` (name, content hash, path), `verdict`, `cause`, `blocked`, `strictness`,
   `findings` (class, severity, target, reason, outcome, review_required), `trace` path,
   `trace_hash`, `usage` (input/output tokens) and `cost_usd`. Parse-refusal JSON uses the same
   envelope minus trace fields.
10. **Exit code** is verdict-only, as documented: `0 CLEAN`, `1 FLAGGED/MALICIOUS/UNVERIFIED`,
    `2` usage/config/environment. `blocked` is reported but never changes the exit code.
11. **Never a traceback**: argparse handles usage; a handled failure prints one line; any unexpected
    `Exception` is caught at the top, printed as `error: <Type>: <message>`, exit 2. Keyboard
    interrupt exits 130 without a traceback.
12. **The key never leaks**: not in stdout/stderr/JSON, not in the trace, not in `JailConfig.env`.
13. **Tests are offline**: `main` accepts injected `model` and `sandbox` for tests; no real network,
    model or sandbox in the suite.

### Should have

14. `--out` creates the directory; the trace path is absolute in the output.
15. `--keep-run-root` prints the run-root path for debugging.

### Nice to have (deferred)

`assay bundle`, `assay install`, config file, `--quiet`, colour, progress, retries, multiple skills.

## Technical considerations

- **Layout**: `src/assay/cli/__init__.py` and `src/assay/cli/main.py` (argparse + orchestration),
  `src/assay/cli/output.py` (human/JSON rendering). Keep orchestration thin; it composes shipped
  functions and contains no detection logic.
- **Seam for tests**: `main(argv, *, model: Model | None = None, sandbox: Sandbox | None = None)`
  with production defaults. No `--fake` flag is exposed to users.
- **Run root**: `tempfile.mkdtemp(prefix="assay-run-")`, removed in a `finally` unless kept. A4's
  capture resolves symlinks against it, so it must exist until capture finishes.
- **Trace path**: absolute; the default resolves against the invocation directory, not the skill's.
- **Cost**: the printed cap and model come from the parsed values, so the user sees them before the
  run starts; the actual cost comes from the outcome.
- **JSON stability**: dict insertion order is irrelevant (`sort_keys`); no timestamps, no run-root
  path, no absolute skill path in the JSON? The skill path is included because it identifies the
  input; the trace path is included because it is the artefact. Byte stability is asserted for the
  same argv and fixtures.
- **No new dependency**: `argparse`, `json`, `sys`, `tempfile`, `shutil`.
- **`.gitignore`**: add `.assay/` (default output directory).

## Risks and open questions

| Risk | L/I | Mitigation |
|---|---|---|
| Required `--max-cost`/prices is friction | Low/Med | One clear error line names the missing value; env fallbacks make CI easy |
| A stale price understates the cap | Med/Med | No bundled table; the user supplies prices and sees them; actual usage is printed |
| `--json` stability breaks when a field is added | Med/Med | Versioned envelope (`schema: 1`); a test pins the exact bytes for a fixture |
| A parse refusal has no `Assessment` | Low/Med | Explicit, documented `WONT_PARSE` envelope; exit 1, never `CLEAN` |
| The real keyed run is still untested | High/Med | The CLI is tested with an injected model; the first real run is the maintainer's, with the cap printed |
| Catching every exception hides bugs | Med/Med | The message includes the exception type; the trace (when captured) is still saved; tests assert no traceback and a named exit |

Open questions:
- Should the human report include the full finding list even when there are many? Yes; a cap would
  hide evidence.
- Should `--json` go to stdout and the human report to stdout too? Yes, stdout for the report,
  stderr for errors.

## Out of scope

- A6 bundle, A7 corpus, A8 adapters, A9 registry.
- Config files, watch mode, progress bars, colour, retries, parallel skills.
- New detection rules or changes to A5's verdict semantics.
- A `--fake` user-facing mode; injection is a test seam only.

## Areas to strengthen before sharing (self-critique)

- 🟡 The CLI adds a second place where the UNVERIFIED cause vocabulary lives (the envelope for
  `WONT_PARSE`/`SANDBOX_UNAVAILABLE`); it must not drift from A5's `UnverifiedCause`.
- 🟡 Required model/price flags make the first run slightly ceremonial. That is deliberate (R5) but
  worth revisiting if it blocks the gate run.
- 🔴 The suite proves orchestration, not the real provider path. The first keyed run remains the
  only proof that the Anthropic tool loop works end to end.
- Question before greenlighting: **should `--max-cost` be required, or default to a printed cap
  (for example $0.50) so the command is one line in the gate run?**
