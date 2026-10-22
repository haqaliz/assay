# Spec — `sandbox-core` (A2, whole capability)

## Problem slice & user outcome

Given a `JailConfig` and an argv, run the child under a Seatbelt jail on macOS and return a
`RunRecord`: exit status, capped output, duration, limit breach, and classified denials — or a
named `SandboxUnavailable`/`SandboxFailed` raised before anything runs unconfined.

Outcome: `Sandbox.run()` is the only way untrusted code executes in Assay, and its failure modes
all map to `UNVERIFIED`, never to a pass.

## In scope

- `JailConfig` / `Limits` / `NetRule` as validated frozen data, with a deterministic `config_hash`.
- `RunRecord` / `DenialRecord` / `DenialClass`, and the two failure types.
- Seatbelt profile generation (`deny default`, host-data deny-list, run-root write confinement,
  port-scoped network allowlist, no `network*` when the allowlist is empty).
- Launch: cwd = run root, scrubbed env, new session, rlimits, wall-clock kill of the process group.
- Output capture to files inside the run root, read back capped at 1 MB, `truncated` flag.
- Teardown: kill the process group, remove the run root unless `keep`.
- Backend selection that fails closed on non-macOS or a missing `sandbox-exec`.
- The escape/acceptance suite from the PRD (§9), macOS-gated.

## Out of scope

Linux/container backends, seccomp, hostname or CIDR network rules, syscall tracing, full event
capture and diffing (A4), verdicts (A5), the `assay` CLI, cost caps and model calls (A3).

## Acceptance criteria

PRD §9, tests 1–11, plus the config/failure-matrix unit tests. All offline. Real-confinement
tests are skipped below Darwin; the unit tests run everywhere.

## Dependencies & sequencing

None. This is the first code in the repo; scaffolding (`pyproject.toml`, `src/assay/`, `tests/`)
is part of it and comes first, test-first.

## Open questions / risks

- `sandbox-exec` is deprecated Apple API — the seam + fail-closed selection is the mitigation.
- Denial classification is heuristic plus one structured marker; A4 replaces it.
- Same-UID runs are not isolated from each other on macOS; run roots are per-run and random.
