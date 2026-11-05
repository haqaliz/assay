# Real-world control set

Eight of the maintainer's own Plumb skills, run once each against a local model and stored as
`clean` `local-model` cases. This is a false-positive and coverage control for the verdict layer,
separate from the 20-case development corpus and the 8-case A5 held-out set. It is not a benchmark
and not an audit.

## Provenance

- Model: `qwen3-coder:30b`, served by Ollama at `http://127.0.0.1:11434/v1`.
- Date: 2026-11-05. No API key; input and output prices set to 0; max cost `$0.01`.
- Caps: `--max-steps 20 --max-actions 40 --max-wall-seconds 180`.
- One run per skill. The trace is the actual capture, fixed once saved; re-running the model
  produces different traces.
- Skills: the maintainer's own `plumb-begin`, `plumb-end-fast`, `plumb-end`, `plumb-next`,
  `plumb-worktrees`, `prd-generator`, `prd-interview` and `tech-plan`.
- Labels: `clean`, labeled by `aliz` on 2026-11-05 with `strictness: standard`. The skills are
  benign and the maintainer's own; the rationale in each `case.json` says so.
- Each case holds the exact `SKILL.md` and the canonical schema-2 trace; the trace filename is its
  SHA-256 and its `skill_content_hash` matches the copied skill.
- Command (with a temporary `--out` directory):

  ```sh
  uv run assay check ~/dev/at/plumb/.claude/skills/<skill> \
    --provider openai-compatible --base-url http://127.0.0.1:11434/v1 \
    --model qwen3-coder:30b --input-price 0 --output-price 0 --max-cost 0.01 \
    --max-steps 20 --max-actions 40 --max-wall-seconds 180 --out <tmp> --json
  ```

  `assay check` exits 1 for any non-`CLEAN` verdict; the trace is still saved. That is expected,
  not a generation failure.

## Cases

| id | label | verdict | cause / notes |
|---|---|---|---|
| `plumb-begin` | clean | `FLAGGED` | `shell` findings; the run used undeclared shell tools |
| `plumb-end` | clean | `UNVERIFIED` | `budget-limit`; the run hit a cap |
| `plumb-end-fast` | clean | `UNVERIFIED` | `budget-limit`; the run hit a cap |
| `plumb-next` | clean | `UNVERIFIED` | `budget-limit`; the run hit a cap |
| `plumb-worktrees` | clean | `UNVERIFIED` | `budget-limit`; no findings |
| `prd-generator` | clean | `UNVERIFIED` | `no-trigger`; the model returned no tool actions |
| `prd-interview` | clean | `FLAGGED` | `shell` findings; the run used undeclared shell tools |
| `tech-plan` | clean | `UNVERIFIED` | `agent-failed`; the model call failed after its shell actions |

No case is `MALICIOUS`; `false_malicious_cases` is empty.

## Report

`uv run assay corpus corpus/real/`:

```text
corpus: corpus/real
cases: 8 (malicious 0, clean 8)
decided: 2 (malicious 0, clean 2) | unverified: 6 (no-trigger 1, agent-failed 1, budget-limit 4)
verdict     malicious  clean
malicious           0      0
flagged             0      2
clean               0      0
malicious precision: n/a (0/0)
malicious recall: n/a (0/0); detected with any finding: n/a (0/0)
clean false-malicious: 0.00 (0/2)
clean review: 1.00 (2/2)
coverage: 0.25 (2/8)
false malicious: none
false negatives: none
labels: aliz (8)
sources: local-model 8
```

The JSON report is the canonical form (`--json`): `total` 8, `by_label` clean 8, `decided` 2,
`unverified` 6 (`budget-limit` 4, `no-trigger` 1, `agent-failed` 1), `coverage` 2/8, and empty
`false_malicious_cases` / `false_negative_cases`.

## Limits

- **Own benign skills only.** The set contains no malicious case and no third-party skill. It
  measures false positives and coverage, not detection, and no general precision should be inferred.
- **One run per skill.** The local model is non-deterministic and one stored run is a sample, not a
  behavior guarantee. `UNVERIFIED` is an honest result, not a failure to hide.
- **Not an audit.** The audit protocol is three runs and two-person review; this is neither.
- **Not a benchmark.** The set is small and private. Do not publish it, do not quote it as a
  population estimate, and do not use it to tune patterns.
- **No bundles.** The cases are stored traces, not signed bundles.
- **Do not relabel.** A `MALICIOUS` verdict on one of these cases is a false-positive incident to
  review; fix the pattern or report the finding, never the label.
