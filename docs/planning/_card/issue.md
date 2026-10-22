# feat sandbox-jail — A2: Sandbox jail

## Brief

> Build A2, the sandbox jail, for the Phase 0 milestone M0.2 in `docs/ROADMAP.md`: a script runs isolated — filesystem writes confined to a run root, network deny-by-default with a per-run allowlist, a scrubbed environment containing no host credentials, and enforced CPU/time/memory limits. Follow `ARCHITECTURE.md`'s "sandbox first" decision and its open question on Seatbelt vs containers — pick one in the PRD with a written rationale and record it in that file. Acceptance tests, all offline: (1) an outbound connection attempt fails *and* is captured as an event, not silently dropped; (2) a write outside the run root fails while one inside succeeds; (3) a planted `ASSAY_TEST_SECRET` is absent from the child's env; (4) a limit breach terminates the run and yields `UNVERIFIED/SANDBOX_FAILED`, never `CLEAN` and never a traceback; (5) escape attempts (path traversal, `/etc` write, reading `~/.ssh`, a subprocess retrying network) are denied and recorded as escape-test cases per R4.

Source: chosen by `assay-next` as the highest-leverage next capability (A2, no dependencies, retires R4, on the Phase 0 critical path). No GitHub issue exists; `gh issue list --state all` is empty.

## Context carried from the pick

- `docs/technical/ARCHITECTURE.md`, Key decisions: *"Sandbox first. Every skill runs only inside the jail. The jail is the first thing built and the most heavily tested; escape attempts are test cases."*
- `docs/ROADMAP.md` M0.2: *"A script runs in an isolated jail: no network, writes confined, no real env vars; escape attempts are captured, not allowed."*
- `docs/technical/CAPABILITY_ROADMAP.md` A2: *"Isolated jail: filesystem confined, network deny-by-default (allowlist per run), no real credentials or env vars, resource and time limits."* Depends on: none.
- `CLAUDE.md` constraint 2: *"No real secrets, no real user data, in the sandbox."*
- `CLAUDE.md` constraint 4 / verdict contract: `UNVERIFIED` with a named cause when the sandbox can't run the skill; never rendered as `CLEAN`.
