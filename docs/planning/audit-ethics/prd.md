# PRD — `audit-ethics` (M2.3 gate: ethics, disclosure and audit protocol)

Status: approved 2026-11-05 (user approved the M2.3 recommendation and the first unit).
Date: 2026-11-05. Pipeline position: the gate before M2.3's first public audit; no code.

## Problem statement

M2.3 is the credibility play: audit real, widely used skills and publish what Assay observed. It is
also the highest-harm milestone. A false `MALICIOUS` on a real author (R2), or publishing before the
author or registry has had a chance to respond (R3), would hurt people and destroy the project's
credibility. The repo has no `ETHICS.md`, no disclosure timeline, no reviewer rule, no publication
checklist, and no rule for handling a wrong finding.

This unit writes that gate. It does **not** run, contact or publish anything about a third-party
skill. The audit itself is a later, human-reviewed unit that must follow this protocol.

For whom: the maintainer running an audit, a second reviewer, an author or registry receiving a
report, and a reader deciding whether to trust a published verdict.

## Goals and success metrics

| Goal | Metric |
|---|---|
| The gate exists | `ETHICS.md`, `docs/audit/PROTOCOL.md`, `docs/audit/finding-template.md` and `docs/audit/README.md` are in the repo |
| The process is followable | The protocol names roles, selection criteria, run count, review, disclosure window, publication contents, corrections and retention |
| Publication is blocked until safe | The protocol requires a second reviewer and a completed disclosure window before any public finding |
| No over-claim | The docs say no third-party audit has run, the maintainer is the only reviewer today, and the gate is a policy, not an enforcement mechanism |
| No collateral change | No code or test changes; the suite stays at 767; README, CLAUDE.md and ROADMAP link the gate and mark M2.3 protocol-ready, not done |

## Users and scenarios

1. **Maintainer starting an audit** — follows the selection and private-run checklist; records the
   exact skill hash, three runs, bundles and model.
2. **Second reviewer** — replays the bundles, checks the finding reproduction and classification,
   and signs off before disclosure.
3. **Author/registry** — receives a private report with the bundle, hash, finding, reproduction and a
   response window; no public issue.
4. **Reader** — sees the published bundle, verdict, strictness, run count, coverage, author response
   and limits; can replay it.

## Requirements

### Must have

1. **`ETHICS.md`** at the repo root:
   - scope (third-party skills; own skills labeled; engine verdict rules still apply);
   - principles: evidence before accusation, no publication without disclosure, reproduce before
     naming, minimize harm, respect terms/consent, publish the limits, correct in public, no
     pay-for-verdict, protect data, stay in the sandbox;
   - explicit prohibitions: no static/model-only finding, no unreproduced finding, no publication
     before contact (except the defined emergency case), no exploit payloads/secrets/PII, no
     out-of-sandbox run, no consumer-subscription automation, no payment for a verdict;
   - process summary, roles, data handling, disclosure timeline, corrections/retractions, contact.
2. **`docs/audit/PROTOCOL.md`**:
   - roles: runner, reviewer (must not be the runner), publisher; the maintainer is the initial
     runner and is not sufficient as the only reviewer for a public finding;
   - selection: public, installable, supported format, popular or risky, terms allow analysis, no
     real credentials; record name, URL, registry, version/commit, skill hash, author/registry
     contact, license/terms, date;
   - private run: workspace outside the repo or `.assay/audits/` (gitignored); exact skill files;
     `assay check` with BYOK or a local model; `standard` strictness; cost/step/action/wall caps;
     **at least three runs per skill**, or until a HIGH finding reproduces; save traces; bundle each
     run with an audit key; record model/provider/date/prices;
   - review: two-person; reviewer replays the bundle (`signature` + `replay`), checks the trace
     evidence, exact hash/version, and reproduction; classify `confirmed` / `false-positive` /
     `inconclusive`; a false `MALICIOUS` stops the audit;
   - disclosure: private contact to author and registry with the bundle or redacted summary, hash,
     finding, reproduction and proposed publication date; default **30 days**, **7 days** for active
     exploitation, extendable by agreement; escalate to the registry if no response; document every
     attempt;
   - publication: only after the window; contents (skill name/version/hash, bundle, verdict,
     strictness, run count, coverage, findings, author/registry response, limits, correction link);
     no PII/secrets/working exploit beyond the minimum; label own skills;
   - corrections/retractions: notify, correct within 7 days, update/retract the bundle, keep a log;
   - records/retention: selection, runs, bundles, reviewer notes, contact log, publication decision;
     private storage; keep at least 12 months after publication;
   - a copyable checklist with every gate item;
   - the emergency exception and its limits.
3. **`docs/audit/finding-template.md`** — status (`private|disclosed|published|corrected|retracted`),
   audit id, skill URL/version/hash, author/registry contact, terms, runner/reviewer, runs/model/
   strictness/caps, per-run verdicts/causes, findings with class/severity/target/outcome/evidence,
   reproduction, classification, contact log, window, publication draft, limits, corrections.
4. **`docs/audit/README.md`** — a short index and status: the gate is in place; **no third-party
   audit has been run or published**; the first audit needs a second reviewer and the disclosure
   steps.
5. **Status sync** — README (Docs list + a short audit-gate status), CLAUDE.md (folder structure and
   a constraint/status line), ROADMAP (M2.3 row: protocol ready, audit not run; a dated progress
   block). Mark M2.3 as gated, not complete.
6. **No third-party action** — this unit does not fetch, run, contact or publish a third-party skill.
   No code or test changes.

### Should have

7. A status vocabulary and a one-line "what may be published" table in the protocol.
8. A note that the protocol is a minimum, not legal advice, and that registry/provider terms and
   local law must be checked per audit.
9. A named contact route: a private GitHub security advisory or the maintainer's profile contact,
   never a public issue for a finding.

### Nice to have (deferred)

A machine-checked audit manifest; an `assay audit` command; a signed audit report; a second-reviewer
roster; a public corrections log page; legal review.

## Technical considerations

- Docs only; no code paths. The existing `check`/`bundle`/`verify`/`corpus` commands are the tools;
  the protocol does not add a new command.
- `.assay/` is already gitignored, so `.assay/audits/` is a safe private workspace. Do not commit
  third-party skill content, traces or contact logs.
- The bundle's `signature` + `replay` is the evidence primitive; the protocol requires the reviewer
  to run both, not to trust a PDF or a screenshot.
- The two-person rule is the real control; until a second reviewer exists, audits stay private. The
  docs must say this plainly rather than implying the gate is enforced by code.

## Risks and open questions

| Risk | L/I | Mitigation |
|---|---|---|
| The maintainer is the only reviewer | High/High | Public findings require a second reviewer; private audits only until then |
| A false `MALICIOUS` harms an author | High/High | Reproduce, two-person review, disclosure, correction/retraction; a false accusation stops the audit |
| Publishing before a fix | High/High | 30-day window (7 for active exploitation), registry escalation, publication checklist |
| Terms or law forbid an analysis | Med/High | Per-audit terms check; no real credentials; no out-of-sandbox run; stop if unclear |
| The policy is not enforced | Med/Med | Checklist + public commitment + second reviewer; no claim of automated enforcement |
| A disclosure window is too short/long | Med/Med | Default 30 days, extendable by agreement; 7 days only for active exploitation |
| Private records leak | Med/Med | `.assay/audits/` (gitignored) or outside the repo; no third-party content in commits |
| Over-claim in the protocol itself | Low/High | Say "no audit has run", "the maintainer is the only reviewer", "not legal advice" |

Open questions (recommendations):

- **O1 — window length.** [30 days default, 7 for active exploitation, extend by agreement.]
- **O2 — second reviewer.** [A named external reviewer before the first public finding; until then,
  private only. Do not invent a name.]
- **O3 — publication format.** [A signed bundle + a short markdown report with limits and the
  response; no raw exploit payloads.]
- **O4 — where private records live.** [`.assay/audits/` (already gitignored) with a 12-month
  retention note; publish only after disclosure.]

Challenge: **a policy document cannot stop the maintainer from publishing.** The real controls are
the second reviewer, the disclosure window and the public correction log. If the first audit has no
second reviewer, it does not publish. Say that in the docs and hold the line.

## Out of scope

- Running, fetching, contacting or publishing any third-party skill.
- A new CLI command, an audit manifest, or any code/test change.
- Legal advice, a bug bounty, a second-reviewer roster, or a public corrections page.
- M2.4 adapters, A8, A9, ETHICS enforcement automation.

## Areas to strengthen before sharing (self-critique)

- 🔴 **Single-reviewer reality.** The protocol's strongest control is not available today. The docs
  must not imply otherwise; the first public finding waits for a second reviewer.
- 🟡 **No enforcement.** The checklist is social. A future `assay audit` command could enforce some
  fields, but it would not enforce ethics.
- 🟡 **Disclosure timing is judgment.** A 30-day default is a proposal, not a standard; state that
  the author/registry can negotiate.
- 🟡 **Legal/terms.** The docs say "check the terms" but cannot resolve them; that is per audit.
- Question before greenlighting: **should the first real audit be limited to skills the maintainer
  wrote or has explicit permission to test?** [Yes for the first run; public third-party audits wait
  for the second reviewer and the disclosure process.]
