# Assay: Ethics and Responsible Disclosure

Assay makes claims about other people's skills. A false accusation can damage an author, mislead
users, and destroy the credibility of the tool. This document is the rule set for any audit of a
skill we did not write. It is a gate: **no public finding may be published unless every step here
and in [`docs/audit/PROTOCOL.md`](docs/audit/PROTOCOL.md) is met.**

No third-party skill audit has been run or published yet. The maintainer is currently the only
reviewer, which is not enough for a public finding. Until a second reviewer is named, third-party
audits stay private.

## Scope

This policy covers any third-party skill, registry listing, or MCP server that Assay runs or reports
on. The maintainer's own skills are in scope for running, but a finding about them must say so
plainly. The engine's verdict contract still governs every result:

- only an observed, sandboxed run may produce a verdict above `UNVERIFIED`;
- `MALICIOUS` needs a captured `HIGH` finding from a real action;
- `UNVERIFIED` is not a pass, and `CLEAN` means "matched declared scope in this run", not "safe".

## Principles

1. **Evidence before accusation.** We publish what the sandbox captured, never what a scan or a
   model guessed from the markdown.
2. **No publication without disclosure.** The author and the registry get the finding and a response
   window before any public report. There is one narrow emergency exception, defined in the protocol.
3. **Reproduce before naming.** A `HIGH` finding is reproduced before it is called confirmed. One
   run is an observation, not a verdict about the skill.
4. **Minimise harm.** We do not publish a working exploit, a secret, personal data, or more detail
   than a reader needs to understand and verify the finding.
5. **Respect terms and consent.** We check the registry and provider terms before running a skill,
   use BYOK or a local model, never automate a consumer subscription, and stop when the terms or the
   law are unclear.
6. **Publish the limits.** Every report names the model, strictness, run count, coverage, the exact
   skill hash, and the fact that a verdict is per-run and `SKILL.md`-only.
7. **Correct in public.** If we get it wrong, we say so, notify the author and registry, correct the
   record, and keep a log.
8. **No pay-for-verdict.** Nobody can buy a `CLEAN`, a delay, or a softer finding. Sponsorship and
   own-skill audits are disclosed.
9. **Protect data.** The sandbox holds no real credentials or user data. Private audit records stay
   private; only the disclosed bundle and report are published.
10. **Stay in the sandbox.** A skill runs only in the jail, under the cost and time caps. We never
    run an untrusted skill against the host, a real account, or a real secret.

## What we will not do

- Publish a finding based only on a static scan, a model's opinion, or a skill's prose.
- Publish a finding we could not reproduce.
- Publish before contacting the author and registry and waiting out the response window, except under
  the protocol's active-exploitation exception.
- Publish exploit payloads, credentials, personal data, or a ready-to-use attack.
- Run a skill outside the sandbox, with real credentials, or against real user data.
- Automate a consumer chat subscription or violate a provider's terms.
- Accept payment, sponsorship, or a favour in exchange for a verdict.
- Name a private individual; only the public author or registry contact is named.
- Claim that a skill is "safe" or "malicious" beyond the observed run.
- Audit a skill we wrote without labelling it as our own.

## Required process

The full procedure, roles, checklists and windows are in
[`docs/audit/PROTOCOL.md`](docs/audit/PROTOCOL.md). In short:

1. **Select** a public, installable skill whose terms allow analysis; record the exact version and
   hash.
2. **Run privately** at least three times, with the model, strictness and caps recorded; save the
   traces and sign a bundle for each run.
3. **Review with two people.** The reviewer replays every bundle (`signature` and `replay`), checks
   the evidence and reproduction, and classifies the finding. A false `MALICIOUS` stops the audit.
4. **Disclose privately** to the author and registry with the bundle, hash, finding, reproduction
   and a proposed publication date. Default window: 30 days; 7 days for active exploitation.
5. **Publish only after the window**, with the author/registry response, the limits, and the
   correction route. No response is published as "no response" with the contact log.
6. **Correct or retract** promptly if the finding is wrong, and keep a public correction log.

## Roles and independence

- **Runner** — selects and runs the skill, keeps the private records.
- **Reviewer** — must not be the runner; replays the bundles, checks reproduction, and signs off.
- **Publisher** — confirms the checklist and publishes. The maintainer can be the runner and
  publisher, but not the only reviewer of a public finding.

Until a second reviewer is named, audits remain private. This is a deliberate limit, not a
formality.

## Data handling

- The sandbox runs with a scrubbed environment, no real credentials, and no real user data.
- Traces may contain skill text and event excerpts. Private audit records live outside the repository
  or under `.assay/audits/` (already gitignored); no third-party skill content, trace, or contact log
  is committed.
- Publish only the bundle and report the author and registry have seen, with secrets and personal
  data removed.
- Keep private records for at least 12 months after publication so corrections can be checked;
  delete earlier where the law or the author asks.

## Disclosure windows

- **Default: 30 days** from the first private contact.
- **Active exploitation: 7 days**, with the registry notified and no unnecessary exploit detail.
- The window can be extended by agreement with the author or registry. It is not shortened to meet a
  publication schedule.
- If there is no response, the protocol requires documented attempts, registry escalation where
  available, and publication after the window with the contact log.

## Corrections and retractions

If a published finding is wrong, we notify the author and registry, publish a correction within 7
days, update or retract the bundle, and keep the correction in a public log. A false `MALICIOUS` is a
serious incident: the audit stops, the cause is reviewed, and the finding is not republished without
a new, reproduced run.

## Contact

Use the repository's private security-advisory channel (GitHub Security → Advisories → New draft, if
enabled) or the maintainer's profile contact. **Do not open a public issue with a finding or a
suspected vulnerability.** Corrections and disclosure replies use the same private route.

## Limits

This document is a policy, not legal advice, and it is not enforced by code. The real controls are
the second reviewer, the disclosure window, and the public correction log. Registry and provider
terms and local law must be checked for every audit; if they are unclear, the audit does not run.
