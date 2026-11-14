# Security Policy

Assay runs untrusted skills in a sandbox, signs the evidence, and makes claims about what a skill
did. We take vulnerabilities in **Assay itself** seriously.

## Reporting a vulnerability

Please **do not open a public issue** for a security vulnerability. Report it privately:

- Use GitHub's **“Report a vulnerability”** (Security tab, private advisory) on this repository, or
- contact the maintainer through the public contact on the repository owner's GitHub profile.

Include what you found, how to reproduce it, the impact, and the version (`assay --version`). We
will acknowledge the report, work on a fix, and credit you if you want. Please give us a reasonable
window to release a fix before public disclosure.

## In scope

- Sandbox escape or a write/read outside the run root.
- A way to forge, truncate, or bypass the capture channel, a trace hash, a bundle signature, or
  `assay verify` replay.
- Secret exposure through the CLI, traces, bundles, reports, logs, or the MCP session.
- Shell or argument injection reaching the host; path traversal.
- A way to obtain `CLEAN` without an observed run that matches the declared scope.
- A way to lower the severity floor, raise the instruction cap, or make a static/model-only verdict.
- MCP session/client issues: framing confusion, request-id confusion, unbounded line/memory use, or
  a teardown that leaves a child process alive.

## Not a vulnerability in Assay

- A skill that behaves badly **inside** the sandbox. That is a finding about the skill; use the
  audit protocol, not a public issue.
- `UNVERIFIED` or `FLAGGED` results, or a `CLEAN` that means "matched declared scope in this run".
  Assay does not claim a skill is safe forever.
- The absence of a native Windows sandbox backend, or the absence of a hosted/registry service.
- Model/provider behavior outside the jail, unless it crosses a documented Assay boundary.

## Third-party audit findings

A suspected vulnerability in **someone else's skill** is not a GitHub issue. Follow
[`ETHICS.md`](ETHICS.md) and [`docs/audit/PROTOCOL.md`](docs/audit/PROTOCOL.md): private runs, a
reviewer who did not run the target, a private disclosure to the author and registry, and the
response window. Do not open a public issue with a finding.

## Design notes

- The sandbox runs with a scrubbed environment and no real credentials or user data. A skill's host
  home, `/private/etc`, and `/Volumes` are denied by the Seatbelt profile; on Linux, `bubblewrap`
  hides `/home`, `/root` and the host `/etc` behind a private mount tree.
- Traces and bundles are content-addressed; `assay verify` checks the signature, the hashes, and
  replays the shipped verdict. A bundle proves integrity and provenance, not that the run happened.
- Instruction findings are capped at `REVIEW`; the four-class floor cannot be lowered.
- MCP manifests declare startup, not behavior. `assay mcp-report` is an observation report, not a
  safety verdict; the server's own syscalls are not fully mediated.
- Private audit records live under `.assay/audits/` and are not committed.

If you find a case where any of the above does not hold, that is exactly the kind of report we want.
