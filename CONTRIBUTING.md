# Contributing to Assay

Thanks for your interest. Assay is an **execution-grounded security verifier for AI agent skills**.
Its value is evidence: a skill runs in a real sandbox against a real agent, what it did is captured,
and that record is checked against what the skill claims. Contributions should strengthen that chain,
not replace it with a static scan or a model's opinion.

Please read [`VISION.md`](VISION.md), [`docs/technical/ARCHITECTURE.md`](docs/technical/ARCHITECTURE.md)
and [`docs/ROADMAP.md`](docs/ROADMAP.md) before a non-trivial change.

## Development setup

Assay is a Python 3.12+ package managed with [`uv`](https://github.com/astral-sh/uv). The sandbox is
Seatbelt on macOS and `bubblewrap` on Linux, so the real sandbox tests require one of those; other
tests run anywhere. CI runs both.

```sh
git clone https://github.com/haqaliz/assay.git
cd assay
uv sync --dev
uv run pytest
uv run assay --help
```

To use the packaged CLI:

```sh
uv tool install assayhq
# or
pip install assayhq
```

### Dependency policy

No new runtime dependency without a concrete justification. The project deliberately uses the
standard library for the MCP client and fixture server; prefer that pattern for small building
blocks.

### Sandbox tests

The real jail tests use `/usr/bin/sandbox-exec` on macOS and `bwrap` on Linux; they skip when the
backend is absent. CI runs macOS Intel and Ubuntu 24.04 (Linux needs `bubblewrap`, `curl` and
`ssh-keygen`). If you change the sandbox, capture, or `SandboxSession`, run the full suite on both
backends before opening a PR.

## Test-first

Assay is built test-first:

1. Write a failing test that captures the desired behavior (RED).
2. Make it pass with the smallest change (GREEN).
3. Refactor with the suite green.
4. Keep `uv run pytest` green before every commit.

A bug fix should reproduce the bug in a test. A new pattern or held-out calibration needs a fresh
held-out set; do not tune on the development corpus.

## Project layout

```
src/assay/
├── ingest/      # SKILL.md, OpenClaw, Cursor .mdc parsing + declared scope
├── sandbox/     # Seatbelt/bubblewrap jails, one-shot runs, SandboxSession
├── agent/       # bounded BYOK model loop and tool surface
├── capture/     # canonical traces, events, diff
├── verdict/     # CLEAN / FLAGGED / MALICIOUS / UNVERIFIED, floor and policy
├── bundle/      # SSH-signed, replayable records
├── corpus/      # labeled benchmark and metrics
├── triage/      # static pre-filter; never a verdict
├── mcp/         # stdio MCP session/client, inspector, report
└── cli/         # assay check | bundle | verify | corpus | triage | mcp | mcp-report
tests/           # one focused module per source area
corpus/          # benchmark, held-out sets, real-world control
docs/            # roadmap, architecture, audit protocol, planning
```

`.assay/audits/` is gitignored and holds private audit records; do not commit or publish it.

## What to contribute

- **Corpus cases.** A labeled synthetic case or a permitted real case is high leverage. Do not add a
  third-party skill without the audit protocol and author/registry terms. A held-out set is a
  one-shot control; a future change needs a fresh one.
- **File-based adapters (A8).** OpenClaw/ClawHub and Cursor rules are built. A new format needs a
  parser, a declared scope, and tests. MCP is **not** an A8 file adapter; it is a separate capability.
- **Verdict and calibration.** Improve detection without lowering the four-class floor, raising the
  `REVIEW` cap for instructions, or making a verdict from text alone. Changes to the verdict contract
  need an explicit design discussion.
- **MCP.** The stdio session/client, inspector and conservative report are built. A manifest-only
  parser is not verification. Start MCP work with a design note.
- **Docs and bugs.** Clarify the limits, fix a broken command, add a regression test.
- **Audit reviewers.** The project is looking for an independent reviewer for a public audit; see
  [issue #31](https://github.com/haqaliz/assay/issues/31). Reviewers must not have authored or run
  the target.

## Pull requests

1. Branch from `master` (convention: `<type>/<id>/<owner>`, for example `feat/skill-adapter/aliz`).
2. Keep the change focused. Add or extend tests.
3. Run `uv run pytest` and keep it green.
4. Update docs when behavior or the public surface changes.
5. Open a PR explaining **what** changed, **why**, and how it was tested. Link an issue when there
   is one.

Non-trivial features start with a short design note or a PRD under `docs/planning/`; the roadmap is
the source of priorities, not a place to invent a new capability.

## Guardrails

- **Execution decides.** A verdict above `UNVERIFIED` needs an observed, sandboxed run. A static
  scan, a model opinion, or a manifest alone is never a verdict.
- **`UNVERIFIED` is not a pass.** `CLEAN` means "matched declared scope in this run", not "safe".
- **`FLAGGED` is a review**, not an accusation.
- **Instruction findings stay capped at `REVIEW`.** The four-class severity floor cannot be lowered.
- **No real secrets or user data in the sandbox.** No consumer-subscription automation.
- **Audit findings stay private** until the author/registry disclosure window and reviewer sign-off.

## Conduct and security

By participating you agree to the [Code of Conduct](CODE_OF_CONDUCT.md). For a vulnerability in
Assay itself, do **not** open a public issue; follow [SECURITY.md](SECURITY.md).

For a finding about a third-party skill, follow [`ETHICS.md`](ETHICS.md) and
[`docs/audit/PROTOCOL.md`](docs/audit/PROTOCOL.md). Do not open a public issue with a suspected
vulnerability in someone else's skill.

## License

Assay is released under the [Apache License 2.0](LICENSE). By contributing you agree that your
contributions are licensed under the same Apache-2.0 terms, including its patent grant.
