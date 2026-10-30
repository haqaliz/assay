# Spec — `verdict-floor` / `core` (A5)

## Problem slice & user outcome

Given a `Skill` and its `Trace`, return one `Assessment`: a verdict, findings with severity and
evidence, a named `UNVERIFIED` cause when undecidable, and whether the run blocks under the chosen
strictness. No CLI, no bundle, no model, no sandbox.

## In scope

- `Verdict`, `FindingClass`, `Severity`, `UnverifiedCause`, `Strictness`, `Finding`, `Assessment`,
  `VerdictError`.
- `FLOOR`, `FloorViolation`, `StrictnessPolicy`, `DEFAULT_POLICY`.
- `assess(skill, trace, *, policy=DEFAULT_POLICY) -> Assessment`.
- Narrow, explicit regex lists for observed dangerous shell commands and instruction candidates.
- Offline unit tests with synthetic skills and traces.

## Out of scope

CLI/exit codes, config files, A6/A7, model judging, static analysis of skill prose beyond the capped
instruction candidate, remediation text, multi-task aggregation.

## Acceptance criteria

1. `Assessment.verdict is UNVERIFIED` iff `cause is not None`; every other verdict has `cause is None`.
   All enum fields are type-checked; `findings` is copied to a tuple; `CLEAN` carries no findings;
   `FLAGGED` carries at least one finding and no `HIGH`; `MALICIOUS` carries at least one `HIGH`;
   every `HIGH` finding has `review_required=True`; an `INSTRUCTIONS` finding is always `REVIEW`.
2. `trace.cause` set → `UNVERIFIED`, `COST_CAPPED` for `cost-capped`, else `AGENT_FAILED`, no
   findings, regardless of events.
3. `TOOL` and `INSTRUCTION` events are not behavior. No `FILE_READ`/`FILE_WRITE`/`NETWORK`/`SHELL`
   event → `UNVERIFIED/NO_TRIGGER`, unless an instruction pattern matched, in which case `FLAGGED`.
4. No findings and any of `scope.files`, `scope.network`, `scope.tools` is `None` →
   `UNVERIFIED/NO_DECLARED_SCOPE`.
5. No findings, all three dimensions declared, at least one behavior event, no trace cause → `CLEAN`.
6. Findings from divergences:
   - `EXCEEDED` file read or write → `UNDECLARED_FILE`, `REVIEW`.
   - `EXCEEDED` network → `UNDECLARED_NETWORK`, `REVIEW`.
   - `UNDECLARED` or `EXCEEDED` shell → `SHELL`, `REVIEW`.
   - `UNDECLARED` file/network → no finding (the run is capped at `UNVERIFIED`).
7. Findings from captured events, independent of declarations:
   - any `SHELL` event with outcome `OK`/`DENIED` whose normalised command matches a dangerous
     regex → `SHELL`, `HIGH`, even when `allowed-tools` declares `Bash` or `Bash(...)`;
   - any `FILE_WRITE` event with an absolute target and outcome `OK`/`DENIED` → `UNDECLARED_FILE`,
     `HIGH`, even when a declared glob (for example `*`) matches it;
   - any event with outcome `DENIED` → at least `REVIEW` in its class, with the denial text in the
     reason, even inside declared scope.
   A `FAILED` outcome never produces `HIGH`. A `HIGH` finding replaces a `REVIEW` finding for the
   same class/target/outcome rather than duplicating it.
8. Dangerous shell regexes (casefolded, NFKD-stripped, whitespace-collapsed):
   - `rm` with options targeting `/` (`rm -rf /`, `rm -fr /`, `rm --recursive --force /`, `rm -rf /*`),
   - a pipe to `sh`/`bash` (optionally via `sudo` or an absolute path),
   - `base64 --decode`/`-d`,
   - `nc -`,
   - `id_rsa` not followed by `.pub`,
   - `/etc/passwd` or `/etc/shadow`.
   Benign lookalikes (`rm -rf /tmp/build`, `| shasum`, `id_rsa.pub`, a quoted `'rm -rf /'`) are not
   `HIGH`.
9. Instruction patterns are searched only in the skill's own text (`skill.body`, `skill.description`,
   and instruction excerpts with `target == "system"`), never in the user task. Patterns: ignore
   previous instructions, ignore all previous, do/don't tell the user, without telling the user,
   override your, system prompt, exfiltrate. One `REVIEW` finding per matched pattern,
   `review_required=True`, never `HIGH`/`MALICIOUS`.
10. `MALICIOUS` iff at least one finding is `HIGH`; `FLAGGED` iff at least one finding and none is
    `HIGH`; both carry no cause.
11. `blocked`: `MALICIOUS` always; `BASELINE` any `HIGH`; `STANDARD` any finding; `STRICT` any
    finding or `UNVERIFIED`. The verdict string is identical across levels for the same evidence.
12. `StrictnessPolicy(level, floors)`: `floors` must be a mapping containing exactly the four classes
    at exactly `FLOOR` (`REVIEW`). Lowering and raising both raise `FloorViolation`; raising
    strictness is done with `level`. A non-mapping, an unknown class or a non-`Severity` value raises
    `FloorViolation`, never a bare `TypeError`.
13. `assess` computes the diff itself; a trace from another skill raises `CaptureError` before any
    assessment.
14. No model, sandbox, clock, network or file I/O in the suite.

## Dependencies & sequencing

Consumes `assay.ingest.Skill`, `assay.capture.{Trace, Diff, Divergence, Event, diff, CaptureError}`.
No new dependency.

## Open questions / risks

- Pattern lists are stubs; A7 tunes them. Precision is unmeasured.
- Shell parsing is out of scope, so an obfuscated command (`$IFS`, encoded payload) can evade the
  patterns; it remains `FLAGGED` at worst, never `CLEAN`, when it exceeds a declared scope.
