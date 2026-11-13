# PRD — Linux sandbox backend (A2 follow-on)

| | |
|---|---|
| **Capability** | A2 follow-on — Linux sandbox backend |
| **Phase / milestone** | Post-v0.1; next platform slice |
| **Slug** | `linux-backend` |
| **Status** | Linux v1 (one-shot, no network) built; MCP sessions and network allowlists are follow-ups |
| **Owner** | aliz |
| **Tracking issue** | [#36](https://github.com/haqaliz/assay/issues/36) |
| **Guardrails touched** | R4 (escape), R2 (false verdict), `CLAUDE.md` constraint 2 (nothing real is reachable) |

---

## 1. Problem Statement

Assay v0.1.0 can only execute on macOS. `select_sandbox()` returns a `SeatbeltSandbox` on
`darwin` and raises `SandboxUnavailable` everywhere else (`src/assay/sandbox/base.py`). That is
the correct fail-closed behavior, but it blocks Linux users and Windows users who could otherwise
use WSL2. The product's claim is execution-grounded; a static-only Linux mode would be a
different product. This slice adds a **real Linux jail**, not a bypass.

For whom: Linux developers and CI; Windows developers via WSL2; the maintainer, who needs the same
evidence shape across platforms; registries that will verify bundles.

## 2. Goals & Success Metrics

| Goal | Success metric | How measured |
|---|---|---|
| Real Linux confinement | A skill runs under `bubblewrap`; writes outside the run root, home reads, network egress, env leakage, symlink escapes and orphan processes are denied | Linux escape suite, real kernel, all must pass |
| Same evidence model | Same `JailConfig`, `RunRecord`, trace/verdict shape; the backend is named in the report | Unit tests + a Linux run compared to macOS |
| Fail closed | No `bubblewrap` / no Landlock network / setup error -> named `SandboxUnavailable` or `SandboxFailed`; no `CLEAN` | Failure-matrix tests |
| No macOS regression | Full macOS suite and escape tests unchanged | CI matrix |
| Windows path | WSL2 detected and documented; no second backend | Docs + a WSL2 smoke test (manual or CI) |
| Honest network model | No silent all-network; UDP/raw denied; `localhost` refusal or documented downgrade | Network tests with a loopback listener |

## 3. User Personas & Scenarios

- **Linux developer.** Installs `assayhq`, runs `assay check SKILL.md`; expects the same verdict as
  macOS.
- **Windows developer.** Uses WSL2; same commands; docs explain the requirement.
- **CI / registry.** Runs `assay check` on Ubuntu; wants a stable exit code and a bundle that names
  its backend.
- **macOS user.** No change; Seatbelt stays the default.

## 4. Requirements

### Must

| # | Requirement |
|---|---|
| M1 | **Backend selection.** Linux iff `bubblewrap` and the required kernel features are available; otherwise `SandboxUnavailable` with a concrete install/kernel message. No unconfined path. |
| M2 | **Filesystem.** `bubblewrap` mount namespace; run root writable; system dirs read-only; hide `/home`, `/root`, and host secrets; protect the `.assay` capture directory; no host writes. |
| M3 | **Network.** Deny by default. `*:port` TCP via Landlock on kernel 6.7+; deny UDP/raw via seccomp when TCP egress is allowed. DNS must be solved explicitly (pre-resolved `/etc/hosts`, a TCP resolver, or a named refusal); never allow all UDP. `localhost:port` is refused in v1 with a named cause (or implemented with a proxy and documented). Older kernels refuse `*:port`; no-network still works. |
| M4 | **Env scrub.** Only `PATH` plus `JailConfig.env`; parent env absent. |
| M5 | **Limits.** `RLIMIT_CPU`, `RLIMIT_FSIZE`, wall clock, process-group kill, no orphan; teardown removes the run root unless `keep`. |
| M6 | **Sessions.** `SandboxSession`, `assay mcp` and `assay mcp-report` use the selected backend, not a hardcoded `sandbox-exec`. |
| M7 | **Backend identity.** `RunRecord` / `SessionRecord` and rendered reports name the backend and network capability; include the backend in `JailConfig` identity so config hashes differ. Do not silently compare a Linux `CLEAN` to a Seatbelt `CLEAN`. |
| M8 | **Fail closed.** Missing `bubblewrap`, missing kernel feature, namespace denial, or setup error is a named failure; never a verdict. |
| M9 | **Denial classification.** `EPERM` / `EACCES` / bwrap / Landlock messages map to the existing `DenialClass`; this remains best-effort classification, not a trace. |
| M10 | **Tests.** Unit tests for argument construction and selection; real Linux confinement tests in CI on Ubuntu 24.04; macOS suite unchanged; no test opens a real network connection except loopback. |
| M11 | **Docs.** Install `bubblewrap`, kernel matrix, WSL2, platform matrix, and what is weaker on Linux. |

### Should

| # | Requirement |
|---|---|
| S1 | `assay sandbox probe` self-check (deferred from A2) for Linux and macOS, usable in CI. |
| S2 | Ubuntu 22.04 job: no-network works; `*:port` refuses with the named cause. |
| S3 | WSL2 detection in `select_sandbox()` / docs; no separate backend. |
| S4 | Run the 20-case corpus on Linux and compare verdicts to macOS; record differences. |

### Nice

| # | Requirement |
|---|---|
| N1 | Docker/Podman fallback if `bubblewrap` is blocked by user-namespace policy. |
| N2 | Localhost proxy for Ollama (`localhost:port`). |
| N3 | Native Windows backend. |

### Out of scope

- Native Windows; Docker-first; hosted runner.
- Syscall tracing or full capture beyond the mediated Toolbox.
- Hostname/IP pinning (port-only everywhere).
- Changing A5 verdicts, the severity floor, or the instruction cap.
- macOS Seatbelt changes beyond the seam.
- A new Python dependency; `bubblewrap` is a system dependency.

## 5. Technical Considerations

### 5.1 The seam

Current:

- `Sandbox` has `run()` only (`src/assay/sandbox/base.py`).
- `SeatbeltSandbox.run()` is the one-shot backend (`src/assay/sandbox/seatbelt.py`).
- `SandboxSession` hardcodes `sandbox-exec` and `build_profile` (`src/assay/sandbox/session.py`).
- `_mcp` and `_mcp_report` pull `sandbox_exec` off the backend with `getattr`
  (`src/assay/cli/main.py`), and `inspect_server()` takes a `sandbox_exec` path
  (`src/assay/mcp/inspect.py`).

Change:

- Add a backend-owned session factory: `Sandbox.start_session(argv, config) -> Session`, or a
  small `SessionBackend` protocol. Keep `run()` for the one-shot Toolbox.
- Remove `sandbox_exec` from the CLI and `inspect_server`; pass the selected backend.
- `SeatbeltSandbox` and `LinuxSandbox` implement both paths.
- Keep the fail-closed `select_sandbox()` contract.
- Move Seatbelt-specific validation out of `JailConfig` (the double-quote ban belongs in the
  profile builder) and make `DEFAULT_PATH` backend-specific (`/usr/local/bin:/usr/bin:/bin` on
  Linux). `NetRule` keeps `*` / `localhost` + port; its docstring becomes backend-neutral.

### 5.2 Linux backend

`LinuxSandbox` builds a `bubblewrap` command:

```text
bwrap
  --die-with-parent --new-session
  --unshare-user --unshare-pid --unshare-ipc --unshare-uts --unshare-cgroup
  --ro-bind /usr /usr --ro-bind /bin /bin --ro-bind /lib /lib --ro-bind /lib64 /lib64
  --ro-bind /etc/ssl/certs /etc/ssl/certs
  --ro-bind /etc/resolv.conf /etc/resolv.conf
  --ro-bind /etc/hosts /etc/hosts
  --ro-bind <allow_read_extra> <allow_read_extra>
  --tmpfs /tmp --dev /dev --proc /proc
  --bind <run_root> <run_root> --chdir <run_root>
  --clearenv --setenv PATH ... [--setenv k v ...]
  [--unshare-net | --share-net]
  -- <launcher> <argv...>
```

- `/etc` is not bound wholesale; bind only CA certs, DNS, hosts, and the passwd/group entries the
  runtime needs. Resolve symlinks when binding DNS files. Test Python and Node TLS/DNS.
- The A3 driver stages the agent runtime into the run root or names it in `allow_read_extra`; a
  runtime under `/home` is not readable by default.
- `--unshare-net` for no egress.
- For `*:port`, `--share-net` plus a Landlock launcher that allows `connect` only on the configured
  TCP ports and denies `bind`/`listen` unless explicitly required. Landlock alone does not cover
  UDP; a seccomp filter denies UDP/raw socket creation.
- **DNS is the unresolved part.** Denying all UDP breaks `getaddrinfo`. Pick one: pre-resolve the
  provider hostnames into `/etc/hosts` and deny DNS; allow TCP/53 to one configured resolver and
  record the weakening; or refuse network runs. Do not allow all UDP to make DNS work.
- `localhost:port` is refused in v1. A host-side proxy or a Unix-socket bridge is a follow-up; do
  not silently widen it to `*:port`.
- The launcher applies `RLIMIT_CPU` / `RLIMIT_FSIZE`, Landlock, seccomp, then `execvp`. Keep it
  small and tested.
- Limits, process-group kill and teardown reuse the existing POSIX code.

### 5.3 Backend identity

- Add `backend: Literal["seatbelt", "bubblewrap"]` and
  `network_mode: Literal["none", "port"]` to `RunRecord` / `SessionRecord` (or a small frozen
  `BackendInfo`).
- Include the backend in `JailConfig`'s identity/hash so the same settings on different backends do
  not collide.
- Trace schema 2 stores only `sandbox_config_hashes`; adding a readable backend field needs a
  schema decision. For this slice, the run/report names it; if the bundle must carry it, make a
  separate schema-3 slice. Do not silently mix backends.

### 5.4 CI and WSL2

- `ubuntu-24.04` (kernel 6.8, Landlock ABI 4+) with `bubblewrap` installed; run the real escape
  suite.
- `ubuntu-22.04` (kernel 5.15) expects no-network only; `*:port` refuses.
- macOS job unchanged.
- Probe the Ubuntu 24.04 `kernel.apparmor_restrict_unprivileged_userns=1` behavior first. If
  `bubblewrap` is blocked, document the AppArmor profile/sysctl or fall back to Docker; do not ship
  a broken backend.
- WSL2: detect `microsoft` in `/proc/sys/kernel/osrelease`; document; test manually.

## 6. Milestones

| # | Milestone | Done when | Estimate |
|---|---|---|---|
| M1 | Seam refactor | `SandboxSession` / CLI / inspect use a backend; macOS tests pass | 1–2 days |
| M2 | bwrap filesystem/env/limits | Linux one-shot run works; escape tests for files/env/limits pass | 3–5 days |
| M3 | Network | no-network + `*:port` TCP + UDP/raw denial; older-kernel refusal | 4–6 days |
| M4 | Sessions/MCP | `assay mcp` / `mcp-report` run under bwrap; no orphan | 2–3 days |
| M5 | Backend identity/report | Linux run names backend/capability; config hash differs | 1–2 days |
| M6 | CI/WSL2/docs | Ubuntu 24.04 real tests, 22.04 refusal, WSL2 docs | 2–3 days |

Total: **2–3 focused weeks**, not a weekend. The security tests are the work.

## 7. Acceptance Tests

1. `test_linux_without_bwrap_fails_closed` — `select_sandbox("linux")` raises
   `SandboxUnavailable`; no argv runs.
2. `test_linux_write_outside_root_denied` — write inside succeeds; `/tmp` / home write fails; no
   file appears.
3. `test_linux_home_and_secret_read_denied` — `/home/*`, `/root/*`, `/etc/shadow` denied; run root
   and staged inputs readable.
4. `test_linux_env_secret_absent` — parent secret absent in the child.
5. `test_linux_no_network` — TCP and UDP egress fail; denial classified.
6. `test_linux_port_allowlist` — TCP to the allowed port works; another port fails; UDP/raw fails
   even on the allowed port.
7. `test_linux_localhost_refused_or_proxied` — v1 refuses with a named cause, or the proxy path
   passes.
8. `test_linux_limit_kills_group` — wall/CPU runaway killed; no orphan; `limit_exceeded` names it.
9. `test_linux_symlink_escape_denied` — symlink to `/etc/passwd` / home denied.
10. `test_linux_session` — MCP fixture starts, lists tools, tears down; no orphan.
11. `test_linux_verdict_matches_macos` — the 20-case corpus produces the same verdict classes on
    both backends, or differences are recorded.
12. `test_linux_dns_path` — a model hostname resolves through the chosen path (pre-resolved hosts
    or TCP resolver); arbitrary UDP is still denied.
13. `test_macos_unchanged` — existing suite and escape tests pass.

## 8. Risks & Open Questions

| ID | Risk | L/I | Mitigation |
|---|---|---|---|
| R4 | Sandbox escape on Linux | Low/Critical | bwrap namespaces + Landlock/seccomp + escape suite; no unconfined path |
| — | Ubuntu 24.04 blocks unprivileged user namespaces | High/Med | Probe first; AppArmor profile/docs; Docker fallback if unavoidable |
| — | Kernel <6.7 has no Landlock network | Med/High | Fail closed for `*:port`; no-network still works; docs |
| — | UDP/raw egress when TCP is allowed | High/High | seccomp deny; test explicitly |
| — | DNS needs UDP/53, which a naive UDP deny breaks | High/Med | Pre-resolve into `/etc/hosts`, allow TCP/53 to one resolver, or refuse; never allow all UDP |
| — | `bubblewrap` missing / not installed | Med/Med | Named `SandboxUnavailable`; install docs; no auto-install |
| — | `localhost` semantics weaker | Med/Med | Refuse in v1; proxy later; record capability |
| — | Divergent verdicts vs macOS | Med/High | Corpus comparison; backend identity; no silent equivalence |
| — | `bubblewrap` supply chain / setuid | Low/High | Use the distro package; no bundled binary; document |
| — | Trace/bundle schema churn | Med/Med | Keep backend identity in `RunRecord` / `JailConfig`; separate schema slice if needed |

Open questions (recommendations):

1. **bwrap first vs Docker first?** bwrap first; Docker only if user namespaces are blocked.
2. **`localhost:port` in v1?** Refuse with a named cause; add a proxy if local Ollama demand is real.
3. **Trace schema now?** No; name the backend in `RunRecord` / reports and include it in the config
   hash. Schema 3 is a separate decision.
4. **WSL2 supported tier?** Documented best-effort; CI on Linux; no separate backend.
5. **Minimum kernel?** 6.7+ for `*:port`; older kernels no-network only.
6. **`assay sandbox probe`?** Yes; it is the self-check for CI and users, already deferred from A2.
7. **DNS path?** Pre-resolve provider hostnames into `/etc/hosts` and deny DNS, or allow TCP/53 to
   one configured resolver and record the weakening. Never allow all UDP.

## 9. Challenges

- **Why not Docker first?** It adds a daemon, image pulls, slower startup, and a root-equivalent
  daemon. `bubblewrap` is a smaller trusted surface and keeps the local-first story. If user
  namespace policy blocks bwrap on common distros, Docker becomes the fallback, not the default.
- **Why not native Windows?** Windows Sandbox/AppContainer is a separate large backend. WSL2 gives
  Windows coverage with the same Linux code; native Windows can be a later slice if demand
  justifies it.
- **Why not static-only Linux?** It would be a different product. Execution decides; a static scan
  is a pre-filter, never a verdict.
- **What if Linux verdicts differ?** Run the corpus, record the differences, and name the backend.
  Do not claim cross-platform equivalence without evidence.
- **What if bwrap is blocked?** Fail closed, document the setup, and keep Docker as a fallback.
  Never add `--no-sandbox`.

## 10. Self-critique

| Dimension | Score | Note |
|---|---|---|
| Problem definition | 🟢 | Directly removes the macOS-only gap without weakening the claim |
| Scope clarity | 🟢 | Linux first; native Windows/Docker/hosted out |
| Feasibility | 🟡 | Depends on the Ubuntu 24.04 user-namespace probe; kernel 6.7+ for network |
| Security | 🟡 | bwrap + Landlock + seccomp is credible but needs real escape tests |
| Demand | 🟡 | Linux is the obvious gap; no user interviews yet |
| Evidence | 🟡 | No Linux probe has been run; the first milestone is a probe, not code |

**Top gaps to close before implementation:** run a `bubblewrap` probe on Ubuntu 24.04 and 22.04;
confirm the Landlock ABI/network behavior on the CI kernel; confirm seccomp UDP denial from a
Python/Node child; solve the DNS path; decide the trace schema question.

Linux v1 is built: `assay check` runs one-shot under `bubblewrap` with no sandbox network. MCP
sessions, a network allowlist and readable backend identity in the trace remain follow-ups; do not
start them before the Nov 17 Product Hunt launch.
