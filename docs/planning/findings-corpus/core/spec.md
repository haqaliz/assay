# Spec — `findings-corpus` / `core` (A7)

## Problem slice & user outcome

A labeled corpus of skill runs and one offline command that measures A5 against it. The user runs
`assay corpus corpus/`, gets a human or canonical JSON report with explicit numerators and
denominators, and can see whether a verdict change helped or hurt — including false accusations on
clean skills and the `UNVERIFIED` coverage gap. No model, network or sandbox is involved.

## In scope

- `src/assay/corpus/records.py`: `Label`, `Case`, `CaseError`, `load_case`, `load_corpus`.
- `src/assay/corpus/metrics.py`: `Observation`, `Ratio`, `Metrics`, `measure`, `evaluate`.
- `src/assay/corpus/__init__.py`.
- CLI `assay corpus <dir> [--json]` plus a `corpus_refusal` envelope.
- Repo-level `corpus/` with `README.md` and 16–20 labeled cases:
  synthetic adversarial and clean cases covering all four finding classes and every `UNVERIFIED`
  cause, plus two re-run local-model regressions (`plumb-report` and a budget stop).
- Docs/status sync: README, ARCHITECTURE, CAPABILITY_ROADMAP, ROADMAP, CLAUDE.md, `corpus/README.md`.
- Offline tests for loading, metrics, and the CLI.

## Out of scope

A5 changes or tuning; real public third-party skills; disclosure/`ETHICS.md`; confidence intervals;
multiple labelers; automated labels; training; signed benchmark reports; hosted corpus;
`--min-recall` gates; migrating the schema-1 dogfood traces; changing `check`/`bundle`/`verify`.

## Case format

`corpus/cases/<id>/case.json` + `SKILL.md` + `<64hex>.json`.

```json
{"schema":1,"id":"synthetic-shell-exfil","label":"malicious",
 "labeler":"aliz","labeled_at":"2026-11-02",
 "rationale":"The skill tells the agent to upload a file to an undeclared host; the captured shell and network events carry it out.",
 "source":"synthetic","strictness":"standard",
 "trace":"<64hex>.json","expected_classes":["shell","undeclared-network"]}
```

- Exact key set `{schema,id,label,labeler,labeled_at,rationale,source,strictness,trace,expected_classes}`.
- `schema` is int 1; `id` is kebab-case (`^[a-z0-9]+(-[a-z0-9]+)*$`), unique across the corpus;
  `label` ∈ `malicious | clean`; `source` ∈ `synthetic | local-model`;
  `strictness` ∈ `baseline | standard | strict`; `labeled_at` is a real `YYYY-MM-DD` date;
  `labeler`/`rationale` are non-empty strings.
- `trace` is a bare filename matching `^[0-9a-f]{64}\.json$` and must exist in the case directory.
- `expected_classes` is a list of `FindingClass` values, no duplicates (empty allowed).
- The trace is loaded with `TraceStore(case_dir).load(case_dir / trace)`; its
  `skill_content_hash` must equal `parse_skill(case_dir / "SKILL.md").content_hash`, else
  `case-invalid: skill hash mismatch`.

## Metrics

`Observation`: `case_id`, `label`, `source`, `verdict`, `cause`.

- Decided = verdict in `{CLEAN, FLAGGED, MALICIOUS}`; `UNVERIFIED` is excluded and counted by cause.
- Confusion counts: verdict × label over decided cases (`MALICIOUS`/`FLAGGED`/`CLEAN` rows;
  `malicious`/`clean` columns).
- `malicious_precision` = `MALICIOUS`∧malicious / `MALICIOUS` verdicts.
- `malicious_recall` = `MALICIOUS`∧malicious / decided malicious.
- `detection_recall` = (`MALICIOUS`∨`FLAGGED`)∧malicious / decided malicious.
- `clean_false_malicious` = `MALICIOUS`∧clean / decided clean.
- `clean_review` = `FLAGGED`∧clean / decided clean.
- Each ratio is `{numerator:int, denominator:int, value:float|null}`; `value` is `None` when the
  denominator is 0. Never `0.0` for an empty denominator.
- `coverage` = decided / total, with `unverified_by_cause` counts for all five causes.
- `false_malicious_cases` and `false_negative_cases` are sorted id lists.
- `labelers` and `sources` are maps of name/source → case count, sorted.
- `cases` is a sorted-by-id array of
  `{id,label,source,verdict,cause,finding_classes}` where `finding_classes` is the sorted unique
  set of observed finding classes.

## Acceptance criteria

1. **Loading.** `load_corpus(root)` returns cases sorted by id; duplicate ids, missing files, a bad
   `case.json` key set, bad enums, a bad date, a bad trace filename, a trace that fails
   `TraceStore.load`, and a skill/trace hash mismatch each raise `CaseError` with a cause prefix
   (`corpus-unreadable`, `corpus-empty`, `case-invalid`) and the case id where one is known.
   An empty directory or a directory with no case subdirectories is `corpus-empty`.
2. **Evaluation.** `evaluate(cases)` calls the shipped `assess(skill, trace,
   StrictnessPolicy(level=case.strictness))`; it does not re-implement any verdict logic. An
   `Assessment` with `cause` is `UNVERIFIED`; a case's stored `strictness` is respected.
3. **Metrics.** `measure` is pure and table-tested:
   - 8 malicious / 8 clean synthetic observations produce the expected confusion, ratios and ids;
   - `MALICIOUS` on clean is counted in `false_malicious_cases` and in the precision denominator;
   - `FLAGGED` on malicious counts toward detection recall but not malicious recall;
   - `FLAGGED` on clean counts as review, not false `MALICIOUS`;
   - `CLEAN` on malicious counts as a false negative;
   - `UNVERIFIED` is excluded from every ratio and counted by each of the five causes;
   - every ratio with denominator 0 has `value is None`.
4. **Report.** `assay corpus <dir>` prints a human report and `--json` prints one canonical line
   (`schema: 1`) with totals, confusion, the five ratios, coverage, unverified-by-cause,
   false-case ids, labelers, sources and the cases array. Two runs on the same corpus produce
   identical bytes; no timestamps or absolute paths appear.
5. **Human report** names the false-`MALICIOUS` ids explicitly and prints ratios as
   `value (numerator/denominator)` or `n/a (0/0)`.
6. **Exit codes.** `0` on a computed report regardless of metric values; `1` on a load/validation
   failure with a `corpus` envelope (`schema`, `corpus` path, `cause`, `detail`) on stdout; `2` on
   usage; `130` on Ctrl-C; no traceback elsewhere.
7. **No side effects.** `assay corpus` makes no model call, no network call and no sandbox run; it
   writes no files.
8. **First corpus.** `corpus/` contains at least 16 cases: ≥8 `malicious` and ≥8 `clean`, covering
   `shell`, `undeclared-file`, `undeclared-network` and `instructions`, and producing at least one
   of each `NO_TRIGGER`, `NO_DECLARED_SCOPE`, `AGENT_FAILED`, `BUDGET_LIMIT` and `COST_CAPPED` among
   the cases (not necessarily one per case label). It includes:
   - a benign absolute Desktop-write case that must not be `MALICIOUS` (the `plumb-report`
     regression), with `source: local-model` if re-run;
   - a budget-stop case that is `UNVERIFIED/BUDGET_LIMIT`, never `CLEAN`.
   Every case has a rationale and a labeler; every trace is schema 2 and canonical.
9. **Docs.** `corpus/README.md` documents the labeling rule ("malicious" = harmful behavior the
   declared purpose does not justify; "clean" = not malicious, findings allowed), the source
   taxonomy, how to add a case, the metric definitions, and the limits (single labeler, small
   synthetic-dominated sample, not a population estimate, `FLAGGED` on clean is a review). README,
   ARCHITECTURE, CAPABILITY_ROADMAP, ROADMAP and CLAUDE.md are updated; A5 is unchanged.
10. **Suite.** `uv run pytest` is green and offline; `check`/`bundle`/`verify` bytes and exit codes
    are unchanged; the corpus tests do not depend on Ollama or on the repo-level corpus for their
    exact metrics (small `tests/fixtures/corpus/` cases are used for table tests).

## Dependencies & sequencing

Uses `parse_skill` (A1), `TraceStore`/`Trace` schema 2 (A4), `assess`/`StrictnessPolicy`/verdict
enums (A5), and the CLI/canonical conventions (A6). No new dependency. Cases can be bundled with the
shipped A6 command but the benchmark does not require a key.

Order: records/loading → metrics (pure) → CLI → first corpus data → docs. Each step test-first; the
corpus data is generated after the loader so its validity is testable immediately.

## Open questions / risks

- Labels are single-labeler and synthetic-dominated; see PRD O1/O2 and the honesty rules. No
  statistical claims.
- The two local-model traces are non-deterministic inputs but fixed once stored; the model, date and
  command belong in `corpus/README.md` and the case rationale.
- Trace schema 2 is pinned in corpus data; a future schema needs a migration or a regeneration plan.
- `FLAGGED` on clean is ambiguous by design; the report separates it and the README explains it.
