# PRD — Native Windows sandbox backend (A2 follow-on)

| | |
|---|---|
| **Capability** | A2 follow-on — native Windows sandbox |
| **Phase / milestone** | Post-v0.1; separate backend, not scheduled |
| **Slug** | `windows-native` |
| **Status** | Draft for review; **not started** |
| **Owner** | aliz |
| **Tracking issue** | [#50](https://github.com/haqaliz/assay/issues/50) |
| **Guardrails touched** | R4 (escape), R2 (false verdict), constraint 2 (nothing real is reachable) |

---

## 1. Problem Statement

Assay executes on macOS (Seatbelt) and Linux (`bubblewrap`). Windows users can run the Linux
backend inside WSL2, but native Windows (`sys.platform == "win32"`) raises `SandboxUnavailable`.
That is the correct fail-closed behavior, but it means a Windows user without WSL2 cannot run
`assay check` or `assay mcp`.

A native Windows backend is **not a port of bwrap**. The process launcher, filesystem confinement,
limits, stdio handling and tool surface are all different. Shipping an untested Windows jail would
be worse than refusing to run.

For whom: Windows developers who cannot use WSL2; CI runners on Windows; the maintainer, who needs a
real Windows confinement test before any support claim.

## 2. Goals & Success Metrics

| Goal | Success metric | How measured |
|---|---|---|
| Real Windows confinement | AppContainer process writes only to the run root; a host canary is unreadable | Windows confinement suite, real AppContainer |
| Limits and teardown | Job Object kills a runaway; no orphan; `limit_exceeded` names the limit | Job Object tests |
| Fail closed | Missing AppContainer/Job Object/setup error -> `SandboxUnavailable`/`SandboxFailed`; no `CLEAN` | Failure-matrix tests |
| Honest network | No network in v1; `http_get` fails closed | Network tests |
| No regressions | macOS and Linux suites unchanged | CI matrix |
| No support claim before evidence | Windows CI probe passes first; docs say WSL2 until then | Windows probe + docs review |

## 3. User Personas & Scenarios

- **Windows developer.** Installs `assayhq`, runs `assay check SKILL.md`; expects a confined run.
- **Windows CI.** Runs `assay check` on `windows-latest`; needs a named refusal if AppContainer is
  unavailable.
- **WSL2 user.** Keeps the existing Linux backend; no change.
- **macOS/Linux user.** No change.

## 4. Requirements

### Must

| # | Requirement |
|---|---|
| M1 | **Backend selection.** `select_sandbox("win32")` returns `AppContainerSandbox` only if the probe succeeds; otherwise `SandboxUnavailable` with WSL2 guidance. No unconfined path. |
| M2 | **AppContainer.** Create a per-run AppContainer profile/SID; launch the child with `PROC_THREAD_ATTRIBUTE_SECURITY_CAPABILITIES`; grant only the run root to the AppContainer SID. |
| M3 | **Filesystem.** Host data is unreadable by default; the run root is writable; staged inputs are readable; the `.assay` capture directory is not writable by the child. |
| M4 | **Job Object.** CPU/wall limits, active-process/memory limits where reliable, kill-on-close, terminate the job on timeout; no orphan. |
| M5 | **Environment.** Scrubbed environment; only `PATH` plus `JailConfig.env`. |
| M6 | **Network.** No network in v1; `http_get` fails closed. WFP or a proxy is a follow-up. |
| M7 | **Tool surface.** Windows equivalents for `read_file`, `write_file`, `run_shell`, `http_get`; no POSIX `/bin/cat`, `/bin/cp`, `/bin/sh` assumptions. |
| M8 | **Session/MCP.** Long-lived stdio session with the same line/timeout/teardown behavior; local stdio MCP servers only. |
| M9 | **Backend identity.** Add `appcontainer` to the allowed `JailConfig`/Trace schema-3 backend values; `network_mode` is `none`. |
| M10 | **Fail closed.** Profile/ACL/attribute/job failures are named failures; no verdict. |
| M11 | **Tests.** Windows unit tests and real AppContainer confinement tests in CI; macOS/Linux unchanged. |
| M12 | **Docs.** Native Windows is not supported until the probe and suite pass; WSL2 remains the recommended path. |

### Should

| # | Requirement |
|---|---|
| S1 | `assay sandbox probe` self-check for Windows (and reuse on macOS/Linux). |
| S2 | In-process file tools on Windows to avoid spawning `cat`/`copy`; keep the trace shape. |
| S3 | Windows CI matrix (`windows-latest`, Python 3.12/3.13). |
| S4 | A WSL2 detection/help message when native AppContainer is unavailable. |

### Nice

| # | Requirement |
|---|---|
| N1 | WFP port allowlist for `http_get` (requires admin or a proxy design). |
| N2 | Native ARM64 Windows. |
| N3 | MSI packaging. |

### Out of scope

- Windows Sandbox / Hyper-V VM backend.
- WFP network filters in v1.
- Native ARM64 and MSI packaging.
- GUI or a Windows service.
- Changing A5 verdicts, the severity floor, or the instruction cap.
- A new Python dependency; use `ctypes`/Win32.

## 5. Technical Considerations

### 5.1 Why this is separate from bwrap

`src/assay/sandbox/process.py` uses POSIX `resource`, `preexec_fn`, process groups and
`killpg`; `src/assay/sandbox/session.py` uses POSIX sessions. The `Toolbox` runs `/bin/cat`,
`/bin/cp`, `/bin/sh` and `/usr/bin/curl`. Windows needs:

- a separate one-shot runner and session (not a conditional inside the POSIX one);
- a Windows tool surface (in-process file read/write, `cmd.exe`/PowerShell for shell, `curl.exe`
  for HTTP if/when network is allowed);
- Win32 process creation with an AppContainer security-capabilities attribute.

### 5.2 AppContainer launch

Use `ctypes` against `kernel32`/`userenv`/`advapi32`:

1. `CreateAppContainerProfile` (or `DeriveAppContainerSidFromAppContainerName` for an existing
   profile) to get the AppContainer SID.
2. Grant the run root to that SID (for example `icacls <run_root> /grant *<sid>:(OI)(CI)M`) and
   remove inherited access where practical.
3. Build a `SECURITY_CAPABILITIES` with no capabilities (no `internetClient`).
4. `InitializeProcThreadAttributeList` +
   `UpdateProcThreadAttribute(PROC_THREAD_ATTRIBUTE_SECURITY_CAPABILITIES)`.
5. `CreateProcessW` with `EXTENDED_STARTUPINFO_PRESENT | CREATE_SUSPENDED |
   CREATE_UNICODE_ENVIRONMENT`, custom stdio pipes and a scrubbed environment block.
6. Assign to a Job Object, then `ResumeThread`.
7. On timeout, `TerminateJobObject`; close handles; delete the profile where appropriate.

### 5.3 Job Object

- `JOBOBJECT_EXTENDED_LIMIT_INFORMATION` with `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`,
  `PerJobUserTimeLimit`, `ActiveProcessLimit` and a memory limit where reliable.
- Wall-clock timeout in the parent; terminate the whole job.
- The record carries `limit_exceeded` and `teardown_error`, like the POSIX runner.

### 5.4 Tool surface

The current `Toolbox` is POSIX-specific. A Windows executor should:

- implement `read_file`/`write_file` in-process (UTF-8, size caps, path normalization) rather than
  spawning `cat`/`copy`;
- run `run_shell` through `cmd.exe /d /s /c` or PowerShell with the same output caps;
- for `http_get`, use `curl.exe` if present, but network is disabled in v1 so it fails closed before
  the process starts;
- keep the same `ToolCall`/`Event`/trace shape.

### 5.5 Backend identity and schema

Trace/bundle schema 3 already carries a backend string. Add `appcontainer` to the allowed values in
`JailConfig`, `Trace`, and the schema tests. `network_mode` is `none` in v1. No new schema version is
needed for the backend value.

### 5.6 Windows CI

- `windows-latest` with Python 3.12/3.13.
- The first job is a **probe**, not the product: create an AppContainer profile, launch
  `cmd.exe /c echo ok`, grant a temp run root, read a canary outside, and assign a Job Object.
- If the runner cannot create AppContainers, the backend stays unreleased and WSL2 remains the path.
- Real confinement tests run only when the probe succeeds.

## 6. Milestones

| # | Milestone | Done when | Estimate |
|---|---|---|---|
| M1 | Windows probe | AppContainer profile + process + ACL + Job Object work on `windows-latest`; canary denied | 2–3 days |
| M2 | One-shot runner | `AppContainerSandbox.run` with pipes, env, limits, teardown, denial classification | 1–2 weeks |
| M3 | Tool surface | `read_file`/`write_file`/`run_shell`/`http_get` on Windows; trace shape unchanged | 3–5 days |
| M4 | Session/MCP | Long-lived stdio session; local MCP fixture | 3–5 days |
| M5 | CI/docs/release | Windows confinement suite, docs, backend identity, release | 3–5 days |

Total: **4–6 focused weeks**, not a weekend. The probe is the gate.

## 7. Acceptance Tests

1. `test_windows_appcontainer_profile` — profile/SID created; launch succeeds.
2. `test_windows_write_inside_only` — write inside the run root succeeds; outside fails; no host file.
3. `test_windows_host_canary_denied` — a canary outside the run root is unreadable.
4. `test_windows_env_secret_absent` — parent secret absent in the child.
5. `test_windows_job_limit` — CPU/wall runaway killed; no orphan; `limit_exceeded` names it.
6. `test_windows_no_network` — TCP/UDP fail; `http_get` fails closed.
7. `test_windows_missing_appcontainer_fails_closed` — named `SandboxUnavailable`; no execution.
8. `test_windows_session` — MCP fixture starts, lists tools, tears down; no orphan.
9. `test_windows_backend_identity` — `RunRecord`/`SessionRecord`/trace say `appcontainer`, `network_mode: none`.
10. `test_macos_linux_unchanged` — existing suites and bundles pass.

## 8. Risks & Open Questions

| ID | Risk | L/I | Mitigation |
|---|---|---|---|
| R4 | AppContainer escape / ACL mistake | Low/Critical | Probe first; least-privilege SID; canary tests; fail closed |
| — | `windows-latest` cannot create AppContainers | High/Med | Probe before code; keep backend unreleased; WSL2 fallback |
| — | Profile/ACL APIs are easy to get subtly wrong | High/High | Small probe, real canary tests, no support claim without CI |
| — | POSIX `process.py`/`session.py`/`Toolbox` assumptions | High/High | Separate Windows runner and tool surface; do not fork the POSIX path in place |
| — | No network in v1 | Med/Med | `http_get` fails closed; WFP/proxy later |
| — | WFP needs admin | Med/High | Do not include WFP in v1 |
| — | No local Windows dev machine | High/Med | CI probe + real Windows tester before release |
| — | Overclaim | High/High | WSL2 stays the documented path until every acceptance test passes |

Open questions (recommendations):

1. **Probe first?** Yes; no product code before M1.
2. **AppContainer profile creation admin?** Probe; if admin is required, document it and fail closed
   without it.
3. **Tool surface?** In-process file tools; `cmd.exe`/PowerShell for shell; `curl.exe` only when
   network lands.
4. **Network v1?** None; WFP later.
5. **WSL2 default?** Yes; native Windows is an optional backend.
6. **Release target?** 0.2.0 or later, after a real Windows confinement suite.

## 9. Out of Scope

- Windows Sandbox / Hyper-V VM.
- WFP filters, proxies, or network allowlists.
- Native ARM64, MSI, GUI, service.
- Windows Server-specific behavior.
- Changes to A5 or the trace/bundle schema version (the backend value fits schema 3).

## 10. Challenges

- **Why not ship now?** An untested Windows jail would be a security claim with no evidence. The
  product's one sentence is execution-grounded; a native Windows backend must be tested on Windows.
- **Why not use Docker?** Daemon dependency, image pulls, and a different trust model; it does not
  remove the need for a Windows process/tool surface.
- **Why not Windows Sandbox?** Pro/Enterprise, VM startup, and automation friction; AppContainer is
  the smaller default if the probe passes.
- **What if AppContainer is unavailable?** Fail closed and point to WSL2. Do not add an unconfined
  mode.
- **What if the probe fails?** Stop. The plan is a probe, not a promise.

## 11. Self-critique

| Dimension | Score | Note |
|---|---|---|
| Problem definition | 🟢 | Removes the native Windows gap without weakening the claim |
| Scope clarity | 🟢 | AppContainer one-shot first; WFP/Sandbox/ARM64 out |
| Feasibility | 🟡 | Unproven until the `windows-latest` AppContainer probe |
| Security | 🟡 | AppContainer + Job Object is credible, but ACLs and launch attributes need real tests |
| Demand | 🟡 | WSL2 already covers many Windows users; demand is unmeasured |
| Effort | 🔴 | 4–6 weeks; not a small port |

This is a plan, not a support claim. **WSL2 remains the supported Windows path** until the Windows
probe and confinement suite pass.
