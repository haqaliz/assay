# Spec — `audit-ethics` / `core` (M2.3 gate)

## Problem slice & user outcome

The repository gains a written, followable gate for third-party skill audits: evidence rules, a
two-person review, a disclosure window, publication limits, corrections and records. A maintainer
can start a private audit without guessing; a reviewer knows what to check; an author/registry knows
what they will receive and when a finding may become public. No third-party skill is run, contacted
or published in this unit.

## In scope

- `ETHICS.md` (root): scope, principles, prohibitions, process summary, roles, data handling,
  disclosure, corrections, contact.
- `docs/audit/PROTOCOL.md`: roles, selection, private run, review, disclosure, publication,
  corrections, records/retention, checklist, emergency exception.
- `docs/audit/finding-template.md`: the private finding record and publication draft.
- `docs/audit/README.md`: index + gate status.
- README, CLAUDE.md, ROADMAP sync: the gate exists; M2.3 is protocol-ready, not complete; no
  third-party audit has run; the maintainer is the only reviewer today.

## Out of scope

Fetching/running/contacting/publishing a third-party skill; a new CLI command; code or test changes;
legal advice; a second-reviewer roster; a bug bounty; a public corrections page; A8/A9.

## Required content (acceptance criteria)

1. **ETHICS.md** states:
   - the verdict contract still governs (`MALICIOUS` needs captured behavior; `UNVERIFIED` is not a
     pass; `CLEAN` is per-run);
   - ten principles: evidence before accusation, no publication without disclosure, reproduce before
     naming, minimize harm, respect terms/consent, publish the limits, correct in public, no
     pay-for-verdict, protect data, stay in the sandbox;
   - explicit prohibitions: static/model-only finding, unreproduced finding, publication before
     contact (except the defined emergency), exploit payloads/secrets/PII, out-of-sandbox runs,
     consumer-subscription automation, payment for a verdict;
   - the process summary and a link to the protocol; roles; data handling; the 30-day/7-day
     disclosure windows; corrections/retractions; a private contact route; the single-reviewer
     limitation.
2. **PROTOCOL.md** covers, in order:
   - roles (runner, reviewer who did not run it, publisher) and the two-person rule;
   - selection criteria and the metadata to record per skill (URL, registry, version/commit, skill
     hash, author/registry contact, license/terms, date);
   - the private workspace (`.assay/audits/` or outside the repo; nothing third-party committed);
   - at least three `assay check` runs per skill (or until a HIGH finding reproduces), with the
     model/provider/strictness/caps recorded, traces saved, and each run bundled and signed;
   - two-person review: replay each bundle (`signature` + `replay`), check the trace evidence and the
     exact hash/version, classify `confirmed`/`false-positive`/`inconclusive`, stop on a false
     `MALICIOUS`;
   - disclosure: private contact to author and registry, bundle or redacted summary, hash, finding,
     reproduction, proposed date; 30 days default, 7 for active exploitation, extendable by
     agreement; registry escalation; contact log;
   - publication: only after the window; required contents (name/version/hash, bundle, verdict,
     strictness, run count, coverage, findings, response, limits, correction link); no PII/secrets/
     working exploit; own skills labeled;
   - corrections/retractions: notify, correct within 7 days, update/retract the bundle, log;
   - records/retention: selection, runs, bundles, reviewer notes, contact log, decision; private;
     12 months post-publication;
   - a copyable checklist covering every gate item;
   - the emergency exception (active exploitation) and that it still requires registry notification
     and no unnecessary exploit detail.
3. **finding-template.md** has fields for status, audit id, skill URL/version/hash, author/registry
   contact, terms, runner/reviewer, run metadata, per-run verdicts/causes, findings with evidence,
   reproduction, classification, disclosure log, publication draft, limits and corrections.
4. **docs/audit/README.md** indexes the three documents and says: no third-party audit has been run
   or published; the first public finding needs a second reviewer and the disclosure steps.
5. **Status sync:** README `## Docs` lists `ETHICS.md` and `docs/audit/PROTOCOL.md`; the status says
   the audit gate is in place and no third-party audit has run. CLAUDE.md folder structure includes
   `ETHICS.md` and `docs/audit/`, and the status/constraints say third-party audits are gated. ROADMAP
   M2.3 is "protocol ready; audit not run" with a dated progress block.
6. **No over-claim:** no document says an audit has been performed, a finding was published, the gate
   is automated/enforced, or the maintainer is a sufficient reviewer.
7. **No code/test change:** `uv run pytest` remains 767 passed; no source or test diff.

## Dependencies & sequencing

Uses the shipped A6 bundle (`signature` + `replay`) as the evidence primitive and the existing
`check`/`corpus` commands. Order: ETHICS → protocol → template/index → status sync → review. The
actual audit is a separate unit after the gate is merged.

## Open questions / risks

- The maintainer is the only reviewer; public findings wait for a second reviewer.
- The protocol is a social gate, not enforcement; a future audit command can enforce fields, not
  ethics.
- The 30-day/7-day windows are proposals, not legal standards; authors/registries can negotiate.
- Terms/law are per audit; the docs say to check and stop if unclear.
- The first audit should be limited to the maintainer's own skills or explicit permission until the
  second reviewer and disclosure process are exercised.
