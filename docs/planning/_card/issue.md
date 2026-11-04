# feat audit-ethics — M2.3 gate: ethics, disclosure and audit protocol

## Brief

Write the gate for any third-party skill audit: `ETHICS.md` at the repo root plus
`docs/audit/PROTOCOL.md` and `docs/audit/finding-template.md`. The protocol covers selection and
terms, private sandboxed runs with a minimum of three runs per skill, signed bundles, two-person
review, reproduction of any HIGH finding, a disclosure window with the author and registry,
publication limits, corrections/retractions, records and retention. No third-party skill is run,
contacted or published in this unit; the gate is the deliverable. Sync README, CLAUDE.md and the
ROADMAP (M2.3 protocol-ready, audit not run). Docs-only: no code, no test changes.

Source: `docs/ROADMAP.md` M2.3 and R3 ("Disclosure process before any publication; ETHICS.md before
the first public audit"), `CLAUDE.md` constraint 6, and the M2.3 recommendation accepted on
2026-11-05. A6/A7 and replay are shipped.

## Context carried from the pick

- The 20-case corpus and the self-proving bundle are shipped; the next credibility step is a
  real-world audit, but publication about a real author is the R3 risk.
- `README.md` has no ethics/disclosure document; `docs/` has no audit directory; M2.3 is unstarted.
- The maintainer is the only reviewer today. The protocol must block public findings until a second
  reviewer exists.
- Constraints: no real secrets or user data in the sandbox; execution decides; `UNVERIFIED` is not a
  pass; no consumer-subscription automation; no pay-for-verdict.
