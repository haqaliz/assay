# PRD — `findings-corpus` (A7: labeled corpus and benchmark)

Status: draft for review. Date: 2026-11-02.
Pipeline position: Phase 2, milestone M2.2. A7 follows A5 (verdict) and A6 (signed record) and
turns the verdict into a measured one. No detection logic changes.

## Problem statement

Assay returns verdicts, but nobody knows how good they are. The 2026-10-31 dogfood produced one
`MALICIOUS` (a false accusation, fixed the same day), one `FLAGGED`, eight `UNVERIFIED`, and zero
`CLEAN`; the shell and instruction pattern lists are explicitly "narrow and uncalibrated until A7"
(`docs/technical/CAPABILITY_ROADMAP.md`). There are no labeled samples, no denominators, and no way
to tell whether a change to A5 improves or degrades it. The 10 dogfood traces exist but are schema 1
and carry no labels; the reports' per-row stop causes disagree with the stored traces.

For whom: the maintainer tuning A5, a reviewer deciding whether a verdict change is safe, and a
future registry/CI consumer that needs a precision number rather than an anecdote.

## Goals and success metrics

| Goal | Metric |
|---|---|
| A labeled corpus exists | At least 16 cases (8 malicious, 8 clean), each with `label`, `labeler`, `labeled_at`, `rationale`, `source`, and a schema-2 trace |
| One command measures it | `assay corpus <dir>` loads every case, verifies skill/trace hashes, re-runs the shipped `assess`, and prints a human or canonical JSON report |
| Denominators are explicit | Every precision/recall is printed as `value (numerator/denominator)`; a zero denominator is `null`/`n/a`, never `0` or `1` |
| `UNVERIFIED` is honest | `UNVERIFIED` is excluded from the decided matrix and reported separately by cause; it is never counted as `CLEAN` or as a negative |
| The dangerous error is visible | False `MALICIOUS` on clean cases is a named metric and the case ids are listed |
| Reproducible | The committed corpus yields byte-identical JSON on repeated runs; no model, network or sandbox is needed to benchmark |
| Label authority is visible | The report prints the labelers and their case counts; a single-labeler corpus says so |

## Users and scenarios

1. **Maintainer changing A5** — runs `assay corpus corpus/`, compares the report before/after, and
   sees whether recall improved at the cost of a false accusation.
2. **Reviewer of a verdict change** — reads the JSON `cases` array and the false-`MALICIOUS` list,
   then opens the named case.
3. **Future registry/CI** — consumes the JSON counts and denominators as the current precision
   statement, with the corpus version (git commit) attached.

## Requirements

### Must have

1. **Corpus layout.** A repo-level `corpus/` (not packaged in the wheel) with:
   ```
   corpus/
     README.md                    # labeling rules, sources, limits, how to add a case
     cases/<case-id>/
       case.json                  # label + provenance
       SKILL.md                   # the exact skill that produced the trace
       <64-hex>.json              # schema-2 trace, filename = content hash
   ```
2. **`case.json` schema 1**:
   ```json
   {"schema":1,"id":"synthetic-shell-exfil","label":"malicious",
    "labeler":"aliz","labeled_at":"2026-11-02",
    "rationale":"…why this is malicious/clean, independent of the verdict…",
    "source":"synthetic","strictness":"standard",
    "trace":"<64hex>.json","expected_classes":["shell"]}
   ```
   - `label` ∈ `malicious | clean`; `source` ∈ `synthetic | local-model`;
     `strictness` ∈ `baseline | standard | strict` (default `standard`);
     `expected_classes` ⊆ the four `FindingClass` values (optional, defaults to empty).
   - Exact key set; unknown keys are a named error.
   - `labeled_at` is `YYYY-MM-DD`; `labeler`, `rationale` and `id` are non-empty; `id` is
     kebab-case and unique.
3. **Loading and validation.** `load_corpus(root)` refuses, by name:
   - a missing/unreadable directory or no cases (`corpus-unreadable`, `corpus-empty`);
   - a case directory missing `case.json`, `SKILL.md` or the named trace (`case-invalid`);
   - a skill whose `content_hash` differs from `trace.skill_content_hash`;
   - a trace that is not schema 2, not canonical, or whose filename is not its hash
     (`TraceStore.load` already enforces the last two);
   - duplicate ids, bad enums, unknown keys, or a `trace` field that is a path rather than a
     bare `<64hex>.json` filename.
4. **Benchmark.** `evaluate(cases)` calls the shipped `assess(skill, trace,
   StrictnessPolicy(level=case.strictness))` — no re-implementation. `measure(observations)` is a
   pure function over `(label, verdict, cause, source, id)` so the statistics are testable without
   skills or traces.
5. **Definitions** (documented in `corpus/README.md`):
   - *Decided clean*: label `clean` and verdict `CLEAN` or `FLAGGED` or `MALICIOUS`.
   - *Decided malicious*: label `malicious` and verdict `CLEAN`/`FLAGGED`/`MALICIOUS`.
   - *`UNVERIFIED`*: excluded from both decided sets, counted by cause.
   - *Malicious precision*: `MALICIOUS` on malicious / all `MALICIOUS` verdicts.
   - *Malicious recall*: `MALICIOUS` on malicious / decided malicious.
   - *Detection recall*: (`MALICIOUS` or `FLAGGED`) on malicious / decided malicious.
   - *Clean false-`MALICIOUS`*: `MALICIOUS` on clean / decided clean (the R2 metric).
   - *Clean review*: `FLAGGED` on clean / decided clean. `FLAGGED` on a clean case is not counted as
     a false accusation; the label is "not malicious", not "no findings".
   - A `FLAGGED` malicious case is a detection, not a confirmed `MALICIOUS`.
6. **Report.** Human and `--json` (one canonical line, `schema: 1`):
   - totals by label; decided vs `UNVERIFIED` by cause;
   - the 3×2 decided confusion matrix (verdict rows `malicious/flagged/clean`, label columns);
   - the five ratios above with numerator/denominator/value (`value: null` when denominator 0);
   - the false-`MALICIOUS` case ids and the false-negative case ids;
   - `labelers` (name → count), `sources` (source → count), and the `cases` array
     (`id`, `label`, `source`, `verdict`, `cause`, `finding_classes`);
   - no timestamps or absolute paths, so identical inputs produce identical bytes.
7. **CLI.** `assay corpus <dir> [--json]`:
   - exit `0` when every case loaded and the report was produced, regardless of the metric values;
   - exit `1` on a named load/validation failure (a `corpus` envelope: `schema`, `corpus`, `cause`,
     `detail`), `2` on usage, `130` on Ctrl-C; no traceback;
   - no network, model or sandbox call.
8. **First corpus content.** Synthetic adversarial and clean cases covering all four finding
   classes and every `UNVERIFIED` cause, plus two re-run local-model regressions:
   - `plumb-report` (benign absolute Desktop write) — must not be `MALICIOUS`;
   - one budget-stop Plumb skill — `UNVERIFIED/BUDGET_LIMIT`, never `CLEAN`.
   The remaining dogfood traces stay historical: they are schema 1 and have no labels. Do not
   migrate them silently.
9. **Docs/status.** `corpus/README.md` (labeling rules, source taxonomy, added cases, limits),
   README status/usage, ARCHITECTURE (`corpus/` built, CLI line, A7 section), CAPABILITY_ROADMAP A7,
   ROADMAP M2.2, CLAUDE.md status. Every claim states the limits below.

### Should have

10. Per-class diagnostics for cases with `expected_classes`: observed vs expected finding classes,
    with FP/FN counts (useful for tuning the list without a second corpus).
11. The JSON `blocked` count by label (shows what strictness would have stopped).
12. A `corpus/README.md` recipe for adding a case, including how to build a canonical trace and
    run `assay bundle` on it for publication.

### Nice to have (deferred)

`--strictness` comparison; Wilson/confidence intervals; multiple labelers and inter-labeler
agreement; filtering by source; a signed benchmark report; `assay corpus --min-recall` as a CI gate;
real public-skill cases (M2.3/R3); training or fine-tuning on the corpus.

## Technical considerations

- **Layout.** `src/assay/corpus/records.py` (`Label`, `Case`, `CaseError`, `load_case`,
  `load_corpus`), `src/assay/corpus/metrics.py` (`Observation`, `Ratio`, `Metrics`, `measure`,
  `evaluate`), and `src/assay/corpus/__init__.py`. The CLI adds a `corpus` subcommand and a
  `corpus_refusal` envelope; `check`/`bundle`/`verify` are untouched.
- **Why not bundles in the corpus.** Cases store the exact `SKILL.md` and the trace, not a signed
  bundle. A bundle needs a private key and a published public key, which would put key management
  into the benchmark and CI. Any case can be bundled for publication with the shipped A6 command;
  the trace is already schema 2. A signed benchmark report is a later slice.
- **Why re-run the two regressions.** The dogfood traces are schema 1 and cannot be loaded by the
  current `Trace`; adding an empty `sandbox_config_hashes` would falsely claim no jail ran. Re-run
  with the local model and store the schema-2 trace with its provenance in `rationale`.
- **Synthetic traces.** Hand-built `Trace`s (no model, no jail) use `sandbox_config_hashes=()` and
  are labeled `source: synthetic`. This is honest: no jail ran, and the events are the fixture.
- **Small N.** 16–20 cases give counts, not a population estimate. The report prints denominators
  and the corpus README says not to read it as a general precision claim.
- **Labels precede the verdict.** The rationale describes the skill's behavior and declared
  purpose, not the observed verdict; the labeler must not copy the verdict into the label. This is a
  process rule in the README, not mechanically enforceable.
- **No new dependency.** `dataclasses`, `json`, `pathlib`, `datetime.date` (parse) only.
- **Data size.** Synthetic traces are small; two local-model traces are tens of KB each. The corpus
  is repo data, not packaged.
- **A5 frozen.** This PR does not change `assess`, `SHELL_PATTERNS`, `INSTRUCTION_PATTERNS`, or the
  severity floor. If the corpus reveals a defect, it becomes a separate unit of work with its own
  before/after report.

## Risks and open questions

| Risk | L/I | Mitigation |
|---|---|---|
| Single labeler and small N produce a false sense of precision | High/High | Report denominators, labelers and sources; state "not a population estimate" in the README and every report header |
| Synthetic cases overfit A5 and measure the fixtures, not real skills | High/Med | Label `source`, include two real local-model regressions, keep real public cases for M2.3, do not tune A5 on the benchmark in this PR |
| `UNVERIFIED` exclusion flatters the metrics | Med/High | Print coverage and unverified-by-cause next to the ratios; never report "accuracy" over all cases |
| A wrong label silently changes the benchmark | Med/Med | Rationale + labeler + date per case; labels are git history; corrections are new commits |
| `MALICIOUS` on a clean case is hidden in an aggregate | High/High | Dedicated false-`MALICIOUS` metric and explicit case ids in both outputs |
| Committing traces leaks run content | Med/Med | Synthetic data and the maintainer's own Plumb skills only; the sandbox forbids real secrets; review before publishing |
| The two dogfood traces are stale and the report's causes disagree | Med/Med | Re-run rather than migrate; store provenance; do not trust the old per-row causes |
| A benchmark CLI becomes a de facto pass/fail gate | Low/Med | Exit 0 on any computed report; a threshold gate is deferred to A9 |

Open questions (recommendations in brackets):

- **O1 — corpus size.** 16 cases (8/8) is the minimum for a first report; do we stop there or aim
  for ~24? [Start at 16–20, all four classes and all four causes; grow with real cases.]
- **O2 — label semantics.** Is `clean` "not malicious" (findings allowed) or "no findings"? [Not
  malicious. `FLAGGED` on a clean case is a review, tracked separately; `CLEAN` is the no-finding
  outcome.]
- **O3 — bundles.** Should every case be a signed bundle? [No; store skill + trace, bundle on
  publication. Key management does not belong in the benchmark.]
- **O4 — CLI default dir.** Require `<dir>` or default to `./corpus`? [Require it; the corpus is
  repo data and `assay` is also a pip-installable tool.]

Challenge (the hard question before greenlighting): **if the corpus is synthetic-dominated and
single-labeled, what does "precision 0.83" mean to anyone but you?** The answer this slice relies
on: it is a reproducible regression measurement and a labeling discipline, not a claim about the
skill population. The report says so, prints N and the source mix, and the real-world corpus arrives
with M2.3. If the number is quoted without those qualifiers, the PRD has failed.

## Out of scope

- Changing A5's detection logic, patterns, severities, or verdict contract; tuning on this corpus.
- Real public third-party skills, public audits, disclosure, `ETHICS.md` (M2.3/R3).
- Confidence intervals, significance tests, multiple labelers, automated/model labels.
- Training, fine-tuning, or using the corpus as a model dataset.
- Signed benchmark reports, hosted corpus, `assay install`, `--min-recall` CI gates (A9).
- Migrating or relabeling the schema-1 dogfood traces.

## Areas to strengthen before sharing (self-critique)

- 🔴 **Label authority is one person.** The corpus is a self-assessment until a second labeler or a
  real-world sample exists. The docs must not imply independent validation.
- 🟡 **Synthetic prevalence is not real prevalence.** Precision depends on the base rate; a
  synthetic 50/50 corpus overstates the meaning of `MALICIOUS` precision for a registry with mostly
  benign skills. Say "on this corpus" every time.
- 🟡 **`FLAGGED` on clean is ambiguous.** It can be a true undeclared behavior or an over-strict
  finding list. The report separates it from false `MALICIOUS`, but the README must explain why.
- 🟡 **Corpus rot.** Stored traces are pinned to schema 2; a future trace schema must include a
  migration plan for corpus data.
- Question before greenlighting: **should the first corpus include 8 clean cases that are actually
  `UNVERIFIED` (no declared scope), or only clean cases that can reach `CLEAN`?** [Include both;
  the coverage gap is part of the measurement, but the precision/recall denominators only use
  decided cases.]
