# PRD — `real-corpus` (M2.3 prep: private real-world control set)

Status: approved 2026-11-05 (next milestone). Date: 2026-11-05.
Pipeline position: A7 corpus follow-on / M2.3 prep. No code or A5 change.

## Problem statement

The 20-case development corpus is 18 synthetic and 2 stored local-model runs. Its reported numbers
are honest but synthetic-dominated, and the M2.3 audit cannot start on third-party skills until a
second reviewer and the disclosure process exist. The safe next step is a **private real-world
control set** from the maintainer's own Plumb skills: real instructions, real local-model runs,
stored as schema-2 traces, labeled `clean`, and reported separately. It measures coverage and false
positives on benign real skills without contacting or publishing anything about a third party.

For whom: the maintainer preparing the first audit; a reviewer checking that Assay does not falsely
accuse benign real skills; the A7 corpus's real-world gap.

## Goals and success metrics

| Goal | Metric |
|---|---|
| A real-world control exists | `corpus/real/` with 8 `local-model` cases from the remaining Plumb skills, one stored run each |
| The labels are honest | Every case is `clean` (the maintainer's own skills) with a rationale; no third-party skill |
| The report is computed | `assay corpus corpus/real/` runs and prints verdicts/coverage; no exact precision claim |
| The dangerous error is visible | No false `MALICIOUS`; if one occurs, it is reported and investigated, never relabeled |
| The main benchmark is untouched | The 20-case `corpus/` report and the A5 held-out set are unchanged |
| No publication/audit claim | Docs say this is a private control, not an audit; no bundles/publication required |

## Users and scenarios

1. **Maintainer** — sees how Assay judges benign real skills before an audit.
2. **Reviewer** — checks the real cases and the false-positive count.
3. **Future audit** — the selection/run/label flow is exercised on own skills before third parties.

## Requirements

### Must have

1. **Selection.** The remaining eight Plumb skills: `plumb-begin`, `plumb-end-fast`, `plumb-end`,
   `plumb-next`, `plumb-worktrees`, `prd-generator`, `prd-interview`, `tech-plan`. The two already in
   the main corpus (`plumb-report`, `plumb-begin-fast`) are not duplicated.
2. **Run.** One `assay check` per skill with the local model:
   `--provider openai-compatible --base-url http://127.0.0.1:11434/v1 --model qwen3-coder:30b
   --input-price 0 --output-price 0 --max-cost 0.01 --max-steps 20 --max-actions 40
   --max-wall-seconds 180 --out <tmp> --json`. The check exits 1 for non-`CLEAN`; the trace is saved.
3. **Case layout.** `corpus/real/cases/<id>/{case.json,SKILL.md,<hash>.json}`, id = skill directory
   name; schema-2 trace; `source:"local-model"`, `label:"clean"`, `labeler:"aliz"`,
   `labeled_at:"2026-11-05"`, `strictness:"standard"`, a rationale about the skill's purpose, and
   `expected_classes: []`.
4. **Report.** `uv run assay corpus corpus/real/` and `--json`; record the exact report. Expected:
   labels clean, some `FLAGGED`/`UNVERIFIED`; **no false `MALICIOUS`**. If one occurs, stop and report
   the case; do not relabel.
5. **Test.** `tests/test_corpus_real.py`: loads 8 cases, all `source=local-model`, all `label=clean`,
   `evaluate` runs, and `false_malicious_cases == ()`. The main 20-case report and the A5 held-out
   test are unchanged.
6. **Docs.** `corpus/real/README.md` (provenance, cases, verdict distribution, limits),
   `corpus/README.md` real-control section, README corpus bullet, CAPABILITY_ROADMAP A7, ROADMAP
   progress, CLAUDE.md.
7. **No third-party action, no publication, no bundle, no code/A5 change.**

### Should have

8. The real report's verdict distribution and coverage are in `corpus/real/README.md`; the main
   benchmark is not mixed with the control.
9. The model/date/command/caps provenance is recorded, like the two existing local cases.

### Nice to have (deferred)

Three runs per skill (the audit protocol, not this control); a second labeler; third-party skills
after the M2.3 gate; bundles/publication; a `--split` report.

## Technical considerations

- **Why own skills.** A third-party audit needs a second reviewer and disclosure; a private control
  of the maintainer's own skills does not. It is the safe way to get real instructions and real
  model behavior into the corpus.
- **Why one run.** The corpus stores one run per skill, like the existing local cases; the audit
  protocol's three-run reproduction is for public findings, not this control. Non-determinism is
  fixed once stored.
- **Why separate.** Mixing real and synthetic cases in the 20-case benchmark would change its
  denominators and the A5 calibration pin without a clean comparison. A separate `corpus/real/`
  keeps the benchmark stable and makes the real control visible.
- **Why no bundles.** A bundle is the publication artifact; this set is private and not published.
  A case can be bundled later if needed.
- **No new dependency.**

## Risks and open questions

| Risk | L/I | Mitigation |
|---|---|---|
| A false `MALICIOUS` on a benign own skill | High/High | The test fails; stop, report, investigate; never relabel |
| One run is not a behavior sample | Med/Med | State it; the control measures coverage/false positives, not recall |
| Own skills are not adversarial | High/Med | The set cannot measure detection; say so; real third-party cases wait for M2.3 |
| Non-determinism | Med/Low | Store the trace; provenance recorded |
| The set becomes a de facto benchmark | Low/Med | Separate directory; README says control, not benchmark |
| Local model unavailable | Low/Med | Stop and report; do not fabricate cases |

Open questions (recommendations):

- **O1 — one run or three?** [One; this is a corpus control, not an audit.]
- **O2 — include the two existing local cases?** [No; they are in the main corpus; do not duplicate.]
- **O3 — publish bundles?** [No; private control, no publication.]
- **O4 — add third-party skills?** [No; M2.3 gate first.]

Challenge: **does a benign own-skill set prove anything about detection?** No. It proves Assay can
run real instructions and does not falsely accuse these benign skills; detection is measured by the
synthetic benchmark and, later, third-party cases. Say it plainly.

## Out of scope

- Third-party skills, publication, disclosure, the audit protocol's three runs/two-person review.
- Bundles, MCP, new formats, A5 changes, a second labeler.
- Changing the 20-case benchmark or the A5 held-out set.

## Areas to strengthen before sharing (self-critique)

- 🔴 **No detection signal.** The set is all clean; it measures false positives/coverage, not recall.
- 🟡 **One run per skill.** A conditional behavior may not trigger; `UNVERIFIED` is honest.
- 🟡 **Own skills.** They are not a random sample and not adversarial; no population claim.
- 🟡 **The local model may hallucinate a dangerous command.** That is a harness/model issue, not a
  skill defect; a false `MALICIOUS` is an incident to review, not a label to change.
- Question before greenlighting: **is a real control useful without a second reviewer?** [Yes, as a
  private corpus control; it is not an audit and makes no public claim.]
