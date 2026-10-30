# PRD — `verdict-floor` (A5: verdict and strictness)

Status: draft for review. Date: 2026-10-30.
Pipeline position: A5 of `docs/technical/CAPABILITY_ROADMAP.md`; depends on A4 (merged). Last engine
capability before the CLI (M1.4) and the bundle (A6).

## Problem statement

A4 answers "what diverged". The product question — *is this skill safe to use?* — has no answer, and
the Phase 0 gate cannot report one. A5 must turn a `Diff` into exactly one of `CLEAN`, `FLAGGED`,
`MALICIOUS`, `UNVERIFIED`, with a named cause, without ever over-claiming and without letting a user
configure the four floor classes away.

For whom: the future `assay check` user, the Phase 0 gate, and A6/A7, which need a verdict to bundle
and to measure.

## Goals and success metrics

| Goal | Metric |
|---|---|
| One verdict, always | Every `assess()` call returns exactly one `Verdict` and, for `UNVERIFIED`, one named `UnverifiedCause` |
| No over-claim | A run with no captured tool events is `UNVERIFIED/NO_TRIGGER`; a run where every dimension is undeclared is `UNVERIFIED/NO_DECLARED_SCOPE`; neither can be `CLEAN` |
| The floor cannot be lowered | A policy that sets any floor class below `REVIEW` raises `FloorViolation` at construction; all four classes are always evaluated |
| `MALICIOUS` needs captured behavior | Every `MALICIOUS` has at least one `HIGH` finding whose divergence came from a captured `OK`/`DENIED` action, and `review_required=True` on the assessment |
| Strictness changes blocking only | `blocked` differs across `BASELINE`/`STANDARD`/`STRICT` while the verdict string for the same evidence stays identical |
| Instructions stay a candidate | An instruction-pattern finding is capped at `REVIEW` (never `HIGH`), so it can never produce `MALICIOUS` |
| Replayable | The assessment is derived from `Skill` + `Trace` alone; no model, sandbox, clock or network in the suite |

Not a goal: a CLI, exit codes, a bundle, a corpus, or a second opinion from a model.

## Users and scenarios

1. **A reviewer** — sees `FLAGGED`, the four findings with their evidence, and whether the run was
   blocked, then decides.
2. **`assay check` later (M1.4)** — maps `blocked` to an exit code and `Verdict` to output.
3. **A6** — bundles the assessment and its influencing hashes.
4. **A7** — counts precision/recall against human labels.

## Requirements

### Must have

1. **Types** (frozen):
   - `Verdict ∈ {CLEAN, FLAGGED, MALICIOUS, UNVERIFIED}`
   - `FindingClass ∈ {UNDECLARED_FILE, UNDECLARED_NETWORK, SHELL, INSTRUCTIONS}`
   - `Severity ∈ {LOW, REVIEW, HIGH}` with a strict ordering helper
   - `UnverifiedCause ∈ {NO_TRIGGER, NO_DECLARED_SCOPE, AGENT_FAILED, COST_CAPPED}`
   - `Finding(class_, severity, target, reason, outcome, review_required)`
   - `Assessment(verdict, findings, cause, blocked, strictness, skill_content_hash, trace_hash)`
2. **`assess(skill, trace, *, policy=DEFAULT_POLICY) -> Assessment`**; computes the A4 diff
   internally, so a caller cannot pair a diff with the wrong trace.
3. **Unverifiable first.** If `trace.cause` is set, return `UNVERIFIED` with `COST_CAPPED` for
   `cost-capped` and `AGENT_FAILED` for every other non-null cause, with no findings.
4. **No behavior.** `TOOL` and `INSTRUCTION` events are not behavior. No file/network/shell event →
   `UNVERIFIED/NO_TRIGGER`, unless an instruction pattern matched, which is `FLAGGED` (req 13).
5. **Findings** from divergences:
   - `EXCEEDED` file read/write → `UNDECLARED_FILE`, `REVIEW`.
   - `EXCEEDED` file **write** whose target is absolute (outside the run root) → `HIGH`.
   - `EXCEEDED` network → `UNDECLARED_NETWORK`, `REVIEW`.
   - `UNDECLARED` or `EXCEEDED` shell → `SHELL`, `REVIEW`. A shell finding survives even when the
     skill declared no tools: it ran shell and never said it would.
   - A `DENIED` outcome keeps the finding; it is a captured attempt. A denied event inside
     declared scope (for example a declared `Bash` whose command the jail stopped) is at least a
     `REVIEW` finding, never `CLEAN`.
6. **MALICIOUS patterns.** A finding is raised to `HIGH` only for a captured `OK`/`DENIED` action
   matching an explicit pattern, independent of what the skill declared (a skill that declares
   `Bash` must not switch the detector off):
   - a normalised shell command matching `rm` targeting `/`, a pipe to `sh`/`bash`, `base64 -d`,
     `nc -`, `id_rsa` (not `.pub`), or `/etc/passwd|shadow`;
   - a file write to a sensitive absolute location (`/etc`, `/private/etc`, `~/.ssh`, launch
     agents, shell profiles), or any absolute write when the skill declared a file scope; a plain
     Desktop/report write with no declared file scope is `REVIEW` (dogfood calibration);
   - nothing else. Network stays `REVIEW` (A5 cannot see payload intent).
   A `FAILED` action never reaches `HIGH`. No pattern is applied to the skill's markdown.
   `MALICIOUS` = at least one `HIGH` finding; `review_required=True`; `blocked=True` everywhere.
7. **Instruction finding.** Scan only the skill's own text (`skill.body` + `skill.description`,
   and instruction excerpts with `target == "system"`) after unicode NFKD stripping, casefolding and
   whitespace collapse, for a small override list (`ignore previous instructions`, `ignore all
   previous`, `do/don't tell the user`, `without telling the user`, `override your`, `system
   prompt`, `exfiltrate`). Any hit → `INSTRUCTIONS` finding at `REVIEW`, `review_required=True`,
   capped so it can never be `HIGH`/`MALICIOUS`. The user task is never scanned: it is our prompt,
   not the skill's.
8. **Missing declared scope.** If there are no findings and any of `files`, `network`, `tools` is
   `None`, return `UNVERIFIED/NO_DECLARED_SCOPE`. A finding wins over a coverage gap (a concrete
   observed divergence is more than a missing baseline).
9. **CLEAN.** No findings, `trace.cause is None`, at least one tool event, all three declared
   dimensions present → `CLEAN`. Anything else is not `CLEAN`.
10. **FLAGGED.** No `HIGH` finding but at least one finding → `FLAGGED`.
11. **Strictness.** `StrictnessPolicy(level: Strictness = STANDARD, floors: Mapping[FindingClass,
    Severity] = FLOOR)`, where `FLOOR` is `REVIEW` for all four classes and every floor is fixed at
    it. `__post_init__` rejects a missing/unknown class, a non-mapping, or any floor that is not
    exactly `FLOOR[class]` with `FloorViolation`; strictness is raised with `level`, not by editing a
    class floor. `blocked` is: `MALICIOUS` always; `BASELINE` → any `HIGH`; `STANDARD` → any
    finding; `STRICT` → any finding or `UNVERIFIED`. The verdict string is identical across levels
    for the same evidence.
12. **Every `HIGH` finding carries `review_required=True`** (so every `MALICIOUS` does on the
    assessment and on its findings); `INSTRUCTIONS` findings also carry it. A `REVIEW` behavior
    finding does not.
13. **No verdict without evidence** except the capped instruction candidate; the instruction finding
    is the only finding that may exist with zero tool events, and it still yields `FLAGGED`, never
    `MALICIOUS`.

### Should have

14. `Severity.rank` ordering so callers do not compare strings.

### Nice to have (deferred)

Localisation, per-finding remediation text, a machine-readable policy file, CLI, exit codes.

## Technical considerations

- **Layout**: `src/assay/verdict/{records,policy,assess,__init__}.py`. `records` = frozen types +
  errors, `policy` = strictness + floor validation, `assess` = the decision function.
- **No new dependency.**
- **Pattern scanning is deliberately narrow and explicit**, and only over *observed* commands or the
  recorded instruction text. It is a candidate signal, never the sole basis for `MALICIOUS` outside
  a captured action.
- **Order of precedence**: harness/budget failure → no events → findings (`MALICIOUS` > `FLAGGED`) →
  coverage gap → `CLEAN`. This order is tested.
- **Determinism**: no timestamps, no randomness; findings keep trace order.
- **Offline**: synthetic `Skill`/`Trace` fixtures; no sandbox or model.

## Risks and open questions

| Risk | L/I | Mitigation |
|---|---|---|
| R2: false `MALICIOUS` on a legitimate skill | Med/High | `MALICIOUS` needs a captured `OK`/`DENIED` action matching a short explicit pattern; `review_required` always; `UNDECLARED` file/network never reaches `MALICIOUS`; dogfood narrowed absolute writes to sensitive paths or a declared scope |
| R1: an empty run is read as safe | High/High | No tool events → `UNVERIFIED/NO_TRIGGER`; undeclared dimensions → `UNVERIFIED/NO_DECLARED_SCOPE`; `CLEAN` requires all dimensions declared |
| The instruction pattern list flags benign prose | Med/Med | Capped at `REVIEW`/`FLAGGED`, always `review_required`; never `MALICIOUS` |
| Strictness becomes a way to lower (or manufacture) the floor | Med/High | Floors are fixed at `REVIEW`; any override (lower or raise) raises at construction; strictness is raised with `level`; all four classes always evaluated |
| A dangerous shell command that matches no pattern is only `FLAGGED` | Med/Med | Honest: `FLAGGED` still blocks under `STANDARD`; the pattern list grows with the corpus (A7) |
| A `HIGH` file write to an absolute path is a legitimate configured output | Low/Med | It was not declared, so it is a finding; `review_required` lets a human clear it |

Open questions:
- Should `strict` also block `CLEAN` runs whose coverage is thin (for example zero file events)? Not
  now: `CLEAN` already requires all dimensions declared and at least one event.
- Should instruction scanning read the full body (A5 has `Skill`) or only the trace excerpts? Both:
  the body is authoritative, the excerpts prove what was delivered.

## Out of scope

- CLI, exit codes, JSON output, config files.
- A6 bundle/signing, A7 corpus, A8 adapters.
- Any model-based judging or static analysis of the skill beyond the capped instruction candidate.
- Remediation advice, severity tuning, localisation.
- Multi-task aggregation.

## Areas to strengthen before sharing (self-critique)

- 🟡 The `MALICIOUS` pattern list is a stub. It is explicit and testable, but it will miss most real
  exfiltration and over-flag a benign `| sh`. The corpus (A7) is how it improves; until then,
  `MALICIOUS` is deliberately rare and review-gated.
- 🟡 `UNDECLARED` file/network divergences produce no finding even though A4 reports them; that is
  the user's chosen semantics (silence caps at `UNVERIFIED`), but A5 must surface the gaps so a
  reviewer sees *why* the verdict is unverified.
- 🔴 The suite can prove the mapping, not the calibration. Precision on real skills is unmeasured
  until A7; do not quote a number.
- Question before greenlighting: **is `FLAGGED` the right verdict for a skill that declares nothing
  and runs shell, or should that be `MALICIOUS`/`UNVERIFIED`? The current answer is a deliberate
  compromise: actionable, but not an accusation.**
