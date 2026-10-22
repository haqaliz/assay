# Deep dig — `sandbox-jail` (A2)

Date: 2026-10-23. Greenfield: no `pyproject.toml`, no `src/`, no `tests/`. Everything below is
from the planning docs plus a live probe run on this machine (macOS 26.5.2, `sandbox-exec`
present, Docker 29.8.2 available, `uv` 0.12.17).

## What is really being asked

A library-level jail, not a product surface. Given a `JailConfig` and an argv, start a child
process that **cannot** touch the host: no writes outside its run root, no network except an
explicit per-run allowlist, no inherited secrets, bounded CPU/memory/time — and a
`RunRecord` that says what happened. Every failure to confine is a named `UNVERIFIED` cause,
never a pass.

It is the second half of the moat (the first being A5's floor) and it retires **R4**
(Low/Critical: untrusted skill reaches the host).

## Where it sits

```
A1 ingest → [A2 sandbox] → A3 driver → A4 capture/diff → A5 verdict → A6 bundle
```

A2 is a dependency of A3 and nothing depends on A2 *except* the whole trust story, so it has no
blocker. A4 consumes the run record; A6 hashes the sandbox config; A5 renders
`UNVERIFIED/SANDBOX_FAILED`.

## The open question, answered by probe (not by preference)

`ARCHITECTURE.md` left Seatbelt vs containers open. Probed `sandbox-exec` directly:

| Probe | Profile | Result |
|---|---|---|
| `/bin/echo` | `(deny default)` | exit 71, `execvp` not permitted — fail-closed |
| `/bin/sh -c 'echo ok'` | `(deny default)` + targeted `file-read*` subpaths | **exit 134 (SIGABRT), no output** |
| same | `(deny default)` + `(allow file-read*)` + `(allow process*)` | exit 0, `ok` |
| Python probe | allow-broad, deny `/Users`,`/Volumes`,`/private/etc`,`/private/var/db`, re-allow run root | runs; home read `EPERM`; `/tmp` write `EPERM`; run-root write OK |
| `socket.connect(("1.1.1.1", 80))` | same | `EPERM` (Errno 1) |
| `echo > /private/tmp/x` | same | `Operation not permitted`, file absent |

Working profile shape (the one the backend should generate):

```scheme
(version 1)
(deny default)
(allow process*) (allow sysctl-read) (allow mach-lookup) (allow signal)
(allow file-read*)
(deny file-read* (subpath "/Users") (subpath "/Volumes")
                 (subpath "/private/etc") (subpath "/private/var/db"))
(allow file-read* (subpath "<run_root>"))
(allow file-write* (subpath "<run_root>") (literal "/dev/null"))
```

Three findings that change the design:

1. **Deny-list beats allow-list on macOS.** Narrow `file-read*` allow-lists kill the child with a
   silent SIGABRT (134) — no error, no capture. Allow-broad + deny-sensitive is what actually
   works, and it fails *closed*. A wrong profile must be treated as `SANDBOX_FAILED`, not as a
   crash and never as a pass.
2. **`getcwd` breaks if cwd is outside the jail.** `sh` printed `getcwd: Operation not permitted`
   before running. The launcher must `cwd=run_root`.
3. **Denials surface as `EPERM`/`Operation not permitted` + nonzero exit, with no host-side log.**
   Seatbelt has no callback into our process. So "captured, not allowed" for A2 means: denied
   (enforced by the kernel) and *classified* from the child's exit/status/stderr into a
   `DenialRecord`. Full, trustworthy event capture is **A4's** job and needs a mediated tool
   surface (the agent's file/net/shell calls pass through Assay's executor), not syscall
   tracing — `dtruss` needs root and SIP off. This must not be over-claimed in the PRD.
4. **Network rules are port-scoped only.** `(remote ip "127.0.0.1:8931")` is rejected at parse
   time (`host must be * or localhost`); `(remote tcp "localhost:8931")` and `(remote tcp
   "*:8931")` work, and a wrong port is denied. So A2 can say "no egress" or "egress on port N",
   never "egress to this host". The PRD's CIDR requirement was dropped for this reason.

**Decision this implies:** ship **Seatbelt as the only A2 backend**, behind a `Sandbox` seam.
It is a platform feature already on the machine, needs no daemon, starts in milliseconds, and is
proven above. A container backend is a *second* implementation (image pull, daemon dependency,
slower, rootless-user mapping) — defer it until Linux support is actually needed. Consequence to
state honestly: **on Linux there is no backend yet, so Assay refuses to run (fail-closed) rather
than pretending; real-confinement tests are macOS-gated.**

## Ambiguities to resolve in the PRD

- **Network allowlist shape.** Seatbelt filters by address/port, not hostname
  (`(allow network-outbound (remote tcp "*:443"))` is host-agnostic). So a per-run allowlist is
  IP/CIDR + port, and A3's "call the model API" must resolve to IPs. Do not promise a hostname
  allowlist we cannot enforce.
- **Memory limit.** `RLIMIT_AS` on macOS is advisory for some allocators; wall-clock kill plus
  `RLIMIT_CPU`/`RLIMIT_FSIZE`/`RLIMIT_NPROC` are the reliable set. Say "bounded", not "hard
  memory cap".
- **What "captured" means at A2** (above) — deny + classify, not full trace.
- **Run-root lifetime.** Delete by default; `--keep` for debugging. Traces/corpus never travel
  between worktrees (see `assay-worktrees`).
- **Exit contract.** A2 returns a `RunRecord`; it does not emit verdicts. A5 owns the mapping,
  but the *cause* vocabulary (`SANDBOX_FAILED`, `SANDBOX_UNAVAILABLE`) starts here.

## Open questions for the user

1. Seatbelt-only now (recommended) vs Docker-first vs both? This fixes the install story.
2. Is "deny + classify" an acceptable A2 definition of escape-capture, with full capture deferred
   to A4's mediated tool surface? (Recommended; anything else needs root or kernel extensions.)
3. Python floor: run on 3.12+ (uv-managed) or support the system 3.9.6? (Recommended 3.12+;
   3.9 is EOL and `subprocess`/`resource` behaviour is what we test.)
