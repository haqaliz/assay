# Spec — `check-cli` / `core` (M1.4)

## Problem slice & user outcome

`assay check <skill>` runs the shipped pipeline end to end and reports one verdict with evidence,
a saved trace, a human or JSON report, and a documented exit code. No new detection logic.

## In scope

- `[project.scripts] assay = "assay.cli:main"`.
- `assay check` argument parsing and validation.
- Orchestration: parse, model, sandbox, run root, drive, capture, store, assess, render, clean up.
- Human report and canonical JSON.
- Parse-refusal and sandbox-unavailable envelopes.
- Offline tests with injected model and sandbox.
- `.gitignore` for `.assay/`.

## Out of scope

A6/A7/A8/A9, config files, watch/quiet/colour/progress, retries, parallel skills, new detection
rules, a user-facing fake mode.

## Acceptance criteria

1. `main(argv=None, *, model=None, sandbox=None) -> int`. `assay check --help` exits 0 via argparse;
   an unknown command exits 2 via argparse.
2. Options and defaults: `--strictness {baseline,standard,strict}` (standard), `--max-cost` (required,
   finite > 0), `--model` (env `ASSAY_MODEL`), `--input-price`/`--output-price` (env
   `ASSAY_INPUT_PRICE`/`ASSAY_OUTPUT_PRICE`, finite >= 0), `--max-steps` (20), `--max-actions` (40),
   `--max-wall-seconds` (300), `--out` (`./.assay/traces`), `--json`, `--keep-run-root`.
3. Missing/invalid model settings or cap, or a missing `ANTHROPIC_API_KEY` when no model is injected:
   one line on stderr and exit 2; no run, no trace.
4. `SkillParseError`: no run, no trace; print an envelope with `verdict: UNVERIFIED`,
   `cause: WONT_PARSE`, skill path and `cause: detail`; exit 1. JSON envelope uses `"schema": 1`,
   `"skill": {"path": ...}`, `"verdict": "unverified"`, `"cause": "wont-parse"`, `"detail": ...`.
5. `SandboxUnavailable`: same envelope with `cause: SANDBOX_UNAVAILABLE`, exit 1; nothing ran.
6. Orchestration order: parse → model/sandbox → private run root (`mkdtemp`) → `task_for` →
   `drive` → `capture` → `TraceStore(out).save` → `assess(StrictnessPolicy(level))` → render →
   remove the run root unless `--keep-run-root`.
7. `trace.cause`: `cost-capped` → `UNVERIFIED/COST_CAPPED`; any other → `UNVERIFIED/AGENT_FAILED`.
   The trace is still saved.
8. Human report (stdout): skill name + first 12 hash chars, `verdict:`, `cause:` (`-` when none),
   `strictness: <level> (blocked: yes|no)`, `findings:` lines `[severity] class target: reason`
   (or `findings: none`), `trace: <absolute path>`, `cost: $x.xxxx (N input, M output tokens)`.
9. JSON report (stdout, one line): canonical `json.dumps(sort_keys=True, separators=(",", ":"),
   ensure_ascii=False)` + `\n`, with `schema`, `skill` ({name, content_hash, path}), `verdict`,
   `cause`, `blocked`, `strictness`, `findings` ([class, severity, target, reason, outcome,
   review_required]), `trace`, `trace_hash`, `usage` ({input_tokens, output_tokens}), `cost_usd`.
   Two identical runs with the same argv and fixtures produce identical bytes.
10. Exit codes: `0` for `CLEAN`, `1` for `FLAGGED`/`MALICIOUS`/`UNVERIFIED`, `2` for
    usage/config/environment, `130` for `KeyboardInterrupt`. `blocked` never changes the code.
11. No traceback: an unexpected `Exception` prints `error: <Type>: <message>` and exits 2. The API
    key never appears in stdout, stderr, the JSON, the trace, or `JailConfig.env`.
12. Tests inject a scripted model and a fake sandbox; no network, real sandbox or model call.
13. `--out` is created if missing; `--keep-run-root` preserves and prints the run root; the default
    trace directory is `./.assay/traces` resolved against the invocation directory.

## Dependencies & sequencing

Composes `parse_skill`, `AnthropicModel.from_env`, `select_sandbox`, `Toolbox`, `drive`, `Budget`,
`ModelPrice`, `task_for`, `capture`, `TraceStore`, `assess`, `StrictnessPolicy`. No new dependency.

## Open questions / risks

- The `WONT_PARSE`/`SANDBOX_UNAVAILABLE` envelopes are CLI shapes, not `Assessment`s; document them.
- The real provider path is only proven by a manual run.
