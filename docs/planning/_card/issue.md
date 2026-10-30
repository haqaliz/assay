# feat check-cli — M1.4: `assay check <skill>`

## Brief

> Build the `assay` CLI and its `check` command for Phase 1 milestone M1.4: one command runs the
> whole pipeline — parse the skill (A1), drive a BYOK agent in the sandbox (A3), capture and diff
> (A4), assess (A5) — writes the trace, prints a human report or byte-stable JSON, and exits with a
> code that reflects the verdict. Add the `assay` console script to `pyproject.toml`. Options:
> `--strictness`, `--max-cost`, `--out`, `--json`, plus the BYOK model settings. No traceback ever
> reaches the user; usage/config errors exit 2, a refused parse exits 1 with a named cause.
> `--json` must be byte-stable for the same inputs. This slice is the product surface of A1–A5 and
> the way the Phase 0 gate run will be performed; it adds no new detection logic.

Source: the last Phase 1 milestone (`docs/ROADMAP.md` M1.4), after A5 merged and the manual keyed run
proved to be a one-command job.

## Context carried from the pick

- `docs/ROADMAP.md` M1.4: *"`assay check <skill>` CLI — exit code reflects verdict; JSON output
  byte-stable"*.
- `docs/technical/ARCHITECTURE.md` CLI shape: `assay check <skill> [--strictness LEVEL]
  [--max-cost USD] [--out DIR] [--json]`; `0 CLEAN`, `1 FLAGGED/MALICIOUS/UNVERIFIED`, `2 usage`;
  *"Never a traceback"*.
- `CLAUDE.md`: BYOK only (no subscription path); `UNVERIFIED` is never rendered `CLEAN`; the suite is
  offline, no model call in tests.
- Shipped: `assay.ingest.parse_skill`, `assay.agent.{AnthropicModel, Toolbox, drive, Budget,
  ModelPrice, task_for}`, `assay.capture.{capture, TraceStore}`, `assay.verdict.{assess,
  StrictnessPolicy}`. `pyproject.toml` has no `[project.scripts]` yet.
