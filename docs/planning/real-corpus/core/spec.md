# Spec — `real-corpus` / `core` (private real-world control)

## Problem slice & user outcome

Eight real Plumb skills are run once each against the local model and stored as `clean` `local-model`
cases under `corpus/real/`. `assay corpus corpus/real/` reports them separately; the 20-case
benchmark and the A5 held-out set are untouched. The maintainer gets a real-world false-positive /
coverage control before any third-party audit.

## In scope

- `corpus/real/cases/<id>/` for the remaining eight Plumb skills, one stored run each.
- `corpus/real/README.md` with provenance, cases, verdict distribution and limits.
- `tests/test_corpus_real.py` (loads 8, all local-model/clean, `evaluate` runs, no false
  `MALICIOUS`).
- Docs: `corpus/README.md` real-control section, README, CAPABILITY_ROADMAP A7, ROADMAP, CLAUDE.md.
- No code, A5, trace/bundle schema or dependency change.

## Out of scope

Third-party skills, publication/disclosure, the audit's three runs/two-person review, bundles, MCP,
new formats, A5 changes, a second labeler, changing the 20-case benchmark or the A5 held-out set.

## Cases

| id | skill | label | source |
|---|---|---|---|
| `plumb-begin` | `plumb-begin` | clean | local-model |
| `plumb-end-fast` | `plumb-end-fast` | clean | local-model |
| `plumb-end` | `plumb-end` | clean | local-model |
| `plumb-next` | `plumb-next` | clean | local-model |
| `plumb-worktrees` | `plumb-worktrees` | clean | local-model |
| `prd-generator` | `prd-generator` | clean | local-model |
| `prd-interview` | `prd-interview` | clean | local-model |
| `tech-plan` | `tech-plan` | clean | local-model |

- `case.json`: `schema:1`, `id` = directory name, `label:"clean"`, `labeler:"aliz"`,
  `labeled_at:"2026-11-05"`, a rationale about the skill's purpose, `source:"local-model"`,
  `strictness:"standard"`, `trace` = the saved filename, `expected_classes: []`.
- `SKILL.md` and the schema-2 trace are the exact files from the run; the trace filename is its hash.

## Run

```sh
uv run assay check ~/dev/at/plumb/.claude/skills/<skill> \
  --provider openai-compatible --base-url http://127.0.0.1:11434/v1 \
  --model qwen3-coder:30b --input-price 0 --output-price 0 --max-cost 0.01 \
  --max-steps 20 --max-actions 40 --max-wall-seconds 180 --out <tmp> --json
```

The check exits 1 for a non-`CLEAN` verdict; the JSON contains the saved `trace` path. Copy that trace
and the skill's `SKILL.md` into the case directory. Do not edit the trace or the skill.

## Acceptance criteria

1. `corpus/real/` has exactly 8 cases; all `source=local-model`, `label=clean`, schema-2 traces whose
   `skill_content_hash` matches the copied `SKILL.md`.
2. `uv run assay corpus corpus/real/` prints a report; `--json` is canonical. The report's verdict
   distribution and coverage are recorded in `corpus/real/README.md`.
3. `false_malicious_cases` is empty. If a run produced `MALICIOUS`, stop and report the case; do not
   relabel or omit it.
4. `tests/test_corpus_real.py` loads 8 cases, asserts the source/label, runs `evaluate`, and asserts
   no false `MALICIOUS`.
5. The main `corpus/` 20-case report and the A5 held-out test are unchanged.
6. Docs: the real control is separate, private, not an audit, not a benchmark; one run per skill;
   own skills only; no publication; no bundles.
7. `uv run pytest` green and offline (the stored traces; no model call in the test).

## Dependencies & sequencing

A1 (skill parse), A3/A4 (the local run/trace), A7 (loader/report), A6 (not used). Order: run → cases
→ report → test → docs.

## Risks

- One run per skill is a sample, not a behavior guarantee; `UNVERIFIED` is honest.
- The skills are benign and own; the set measures coverage/false positives, not detection.
- A false `MALICIOUS` is an incident: stop and review; never relabel.
- The local model/run is non-deterministic; the stored trace is fixed.
- The set is small and not a population estimate.
