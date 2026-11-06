# Audit

The gate for third-party skill audits.

- [`../../ETHICS.md`](../../ETHICS.md) — principles, prohibitions, disclosure and corrections.
- [`PROTOCOL.md`](PROTOCOL.md) — selection, private runs, two-person review, disclosure, publication,
  records and the checklist.
- [`finding-template.md`](finding-template.md) — the private finding record and publication draft.

**Status: no third-party skill audit has been run or published.** A private own-skill **runner dry
run** was executed on 2026-11-06: five Plumb skills, three runs each, 15 signed bundles, all
`signature + replay` verified; 9 `FLAGGED`, 6 `UNVERIFIED` (`model-failed`), 0 `HIGH`/`MALICIOUS`.
**Reviewer sign-off was not performed (unreviewed), so it supports no finding and is not a public
audit.** Records are private under `.assay/audits/` (gitignored). The maintainer is currently the
only reviewer, which is not enough for a public finding. The first public audit needs:

1. a second reviewer who did not run the skill;
2. a terms check for the selected registry/provider;
3. at least three private runs per skill, each with a signed bundle that verifies and replays;
4. a reproduced `HIGH` finding;
5. a private disclosure to the author and registry and the response window.

Until then, any audit stays private. Start with the maintainer's own skills or a skill whose author
has explicitly allowed the test. Do not open a public issue with a finding.

This is a policy, not legal advice, and it is not enforced by code. The second reviewer, the
disclosure window and the public correction log are the controls.
