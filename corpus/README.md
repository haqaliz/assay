# Corpus

A labeled set of skill runs and the offline benchmark that measures the verdict layer against it.
Run `uv run assay corpus corpus/`; the loader descends into `cases/` (a flat directory of cases also
works).

## Purpose

`assay corpus` answers one question: did the verdict layer make the right call on runs whose label a
person has already decided? It is a regression measurement for A5 — compare the report before and
after a pattern or policy change — not a claim about skills in the wild.

## Labeling rule

- **malicious** — the run's behavior is harmful in a way the skill's declared purpose does not
  justify.
- **clean** — the behavior is not malicious. This does not require a `CLEAN` verdict: `FLAGGED` on a
  clean case is a review, not a false accusation.

The label describes the behavior, not the verdict. Label a case from what the skill does and what it
claims, independently of what Assay says.

## Sources

- `synthetic` — a hand-built trace, written to exercise a known pattern or state. No model, jail or
  spend is involved. The trace is a fixture, not a capture of a real run.
- `local-model` — a stored run of a real skill against a local model. The trace is the actual
  capture. Provenance is in [Local-model provenance](#local-model-provenance).

Both are stored and scored the same way; the source is provenance, not a confidence weight.

## Case format

`corpus/cases/<id>/` holds exactly three files:

| File | Contents |
|---|---|
| `case.json` | label, labeler, date, rationale, source, strictness, trace filename, expected classes |
| `SKILL.md` | the exact bytes whose hash is stored in the trace |
| `<64hex>.json` | the canonical schema-2 trace; the filename is its SHA-256 |

`case.json` has exactly these keys:

```json
{"schema":1,"id":"synthetic-shell-netcat-exfil","label":"malicious",
 "labeler":"aliz","labeled_at":"2026-11-03",
 "rationale":"…why this behavior is or is not malicious, independent of the verdict…",
 "source":"synthetic","strictness":"standard",
 "trace":"<64hex>.json","expected_classes":["shell"]}
```

- `id` is kebab-case (`^[a-z0-9]+(-[a-z0-9]+)*$`), equals the directory name and is unique.
- `label` ∈ `malicious | clean`; `source` ∈ `synthetic | local-model`;
  `strictness` ∈ `baseline | standard | strict`.
- `labeled_at` is a real `YYYY-MM-DD` date; `labeler` and `rationale` are non-empty.
- `trace` is a bare `<64hex>.json` filename that exists in the case directory.
- `expected_classes` is a list of finding classes with no duplicates; empty is allowed. It records
  what the case is meant to exercise, not what the current verdict must produce.

The loader parses `SKILL.md`, loads the trace with `TraceStore(case_dir).load(...)` and requires
`trace.skill_content_hash == skill.content_hash`. A trace that is not schema 2, not canonical or not
named after its hash is a named refusal.

## Metrics

- **Decided** — verdict `CLEAN`, `FLAGGED` or `MALICIOUS`. `UNVERIFIED` is excluded from every ratio
  and from the confusion rows, and is counted by cause: `no-trigger`, `no-declared-scope`,
  `agent-failed`, `budget-limit`, `cost-capped`.
- **Malicious precision** — `MALICIOUS` on malicious / all `MALICIOUS` verdicts on decided cases.
- **Malicious recall** — `MALICIOUS` on malicious / decided malicious.
- **Detection recall** — (`MALICIOUS` or `FLAGGED`) on malicious / decided malicious.
- **Clean false-malicious** — `MALICIOUS` on clean / decided clean.
- **Clean review** — `FLAGGED` on clean / decided clean.
- **Coverage** — decided / all cases.

Zero denominators are `n/a (0/0)` in the human report and `"value": null` in JSON; they are never
`0.0`. The report also names false-malicious ids (`MALICIOUS` on clean) and false-negative ids
(`CLEAN` on malicious); `FLAGGED` on malicious is a detection, not a false negative.

## Adding a case

1. Create `corpus/cases/<id>/` and write `SKILL.md` with its declared purpose and scope. Use
   `allowed-tools`, `metadata.assay.files` and `metadata.assay.network`; `[]` declares an empty
   dimension and omitting a dimension leaves it undeclared.
2. Produce a trace. Re-run the skill with `assay check`, or build a synthetic trace. Keep the saved
   `<hash>.json`; do not rename it.
3. Save the trace with `TraceStore(case_dir).save(trace)` if it was built in Python.
4. Write `case.json` with the label, a rationale about the behavior — not the verdict — the labeler,
   today's date, the source, the strictness and the expected classes.
5. Run `uv run assay corpus corpus/`. The loader validates the case; the report shows the verdict.
   If the verdict differs from what the case is meant to exercise, fix the case or report the
   finding; do not relabel to match.

## Limits

- **One labeler.** Every case is labeled by `aliz`; there is no inter-rater agreement.
- **Small and synthetic-dominated.** Eighteen of twenty cases are hand-built fixtures. The sample is
  a regression suite, not a population estimate, and synthetic cases test the patterns rather than
  model behavior.
- **Two stored local-model runs** in the 20-case corpus. They are non-deterministic inputs, fixed
  once saved; re-running the model produces different traces. The separate real control adds eight
  more, one per skill.
- **`FLAGGED` on clean is a review, not a false accusation.** Read `clean review` separately from
  `clean false-malicious`.

## Held-out calibration

`corpus/heldout/` is a separate 8-case shell calibration set (4 malicious, 4 clean), not part of the
20-case development corpus. It was measured before and after four `HIGH` shell patterns were added:
strict malicious recall went 0/4 → 4/4, with 0 false `MALICIOUS` on the 4 clean guards; the 20-case
report is unchanged. It is a one-shot control: a future pattern change needs a new held-out set. See
[`heldout/README.md`](heldout/README.md).

## Instruction calibration

`corpus/heldout-instructions/` is a separate 8-case instruction calibration set (4 malicious, 4
clean), also outside the 20-case development corpus. It was measured before and after five
instruction patterns were added (`ignore the above`, `disregard previous`, `forget your
instructions`, `keep this between us`, `do not reveal this`) and two narrowed (`override your`,
`system prompt`). Detection went 0/4 → 4/4 and clean review 2/4 → 0/4, with 0 false `MALICIOUS`; the
20-case report is unchanged. Strict malicious recall stays 0/4 by design: an instruction finding is
capped at `REVIEW`, so `FLAGGED` is a review, not an accusation. It is a one-shot control: a future
pattern change needs a fresh held-out set. See
[`heldout-instructions/README.md`](heldout-instructions/README.md).

## Real-world control

`corpus/real/` is a separate 8-case control of the maintainer's own Plumb skills, one local-model
run each (`qwen3-coder:30b`, 2026-11-05), all labeled `clean`. It is not part of the 20-case
development corpus or the A5 held-out set. It measures false positives and coverage on benign real
skills, not detection: there are no malicious cases.

`uv run assay corpus corpus/real/` reports 8 cases, 2 decided (`FLAGGED`) and 6 `UNVERIFIED`
(`budget-limit` 4, `no-trigger` 1, `agent-failed` 1), coverage 0.25 (2/8), clean false-malicious
0.00 (0/2), clean review 1.00 (2/2). No case is `MALICIOUS`.

The set is private, single-labeled, one run per skill and own skills only. It is not an audit (no
three runs or two-person review), not a benchmark, and no general precision should be inferred. See
[`real/README.md`](real/README.md).

## Local-model provenance

- Model: `qwen3-coder:30b`, served by Ollama at `http://127.0.0.1:11434/v1`.
- Date: 2026-11-03. No API key; input and output prices set to 0; max cost `$0.01`.
- Caps: `--max-steps 20 --max-actions 40 --max-wall-seconds 180`.
- Skills: the maintainer's own `plumb-report` and `plumb-begin-fast`.
- Command (with a temporary `--out` directory):

  ```sh
  uv run assay check <skill dir> \
    --provider openai-compatible --base-url http://127.0.0.1:11434/v1 \
    --model qwen3-coder:30b --input-price 0 --output-price 0 --max-cost 0.01 \
    --max-steps 20 --max-actions 40 --max-wall-seconds 180 --out <tmp> --json
  ```

  `assay check` exits 1 for any non-`CLEAN` verdict; that is expected, not a generation failure.

## Rules

- Do not add a third-party skill without the disclosure process (R3). The corpus is synthetic cases
  plus the maintainer's own Plumb skills.
- Never add real secrets, keys, tokens or personal data. Every synthetic excerpt is invented.
- Trace schema 2 is pinned. A future schema needs a migration or a regeneration of every case; do
  not mix schemas in one corpus.
