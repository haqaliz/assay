# Audit Protocol

The step-by-step gate for a third-party skill audit. Read
[`ETHICS.md`](../../ETHICS.md) first. If a step cannot be met, the audit stops or stays private; it
does not publish.

No third-party audit has been run under this protocol. The maintainer is the only reviewer today;
a public finding requires a second reviewer who did not run the skill.

## Roles

| Role | Responsibility |
|---|---|
| **Runner** | Selects, fetches and runs the skill; keeps the private records; drafts the finding. |
| **Reviewer** | Must not be the runner. Replays every bundle, checks the evidence and reproduction, classifies the finding, signs off. |
| **Publisher** | Confirms the checklist and publishes. Can be the runner, but not the only reviewer. |

The two-person rule is the control. Until a second reviewer is named, audits remain private.

## 1. Select

Choose a skill that is:

- public and installable;
- in a format Assay supports (Claude Code `SKILL.md` first);
- worth the risk: widely used, recently submitted, or flagged by a cheap pre-filter;
- allowed by the registry and provider terms, with no real credentials required.

Record in `.assay/audits/<audit-id>/selection.md`:

- skill name, registry URL, version or commit, exact `SKILL.md` hash;
- author and registry security contact (public);
- license and the terms checked, with the date;
- runner, date, and why this skill was selected.

Do not run a skill whose terms are unclear or whose author cannot be identified well enough to
disclose to. Do not fetch private, paid, or credential-gated skills.

## 2. Run privately

Use a private workspace under `.assay/audits/<audit-id>/` (gitignored) or outside the repository.
Nothing third-party is committed: no skill files, traces, bundles, or contact logs.

1. Save the exact skill files and compute the `SKILL.md` hash. Note the version/commit.
2. Use a dedicated audit key, not a personal signing key:
   `ssh-keygen -t ed25519 -N '' -C assay-audit-<id> -f .assay/audits/<audit-id>/key`.
3. Run `assay check` **at least three times** per skill, or until a `HIGH` finding reproduces:
   ```sh
   uv run assay check <skill> \
     --provider openai-compatible --base-url http://127.0.0.1:11434/v1 \
     --model <model> --input-price <usd-per-mtok> --output-price <usd-per-mtok> \
     --max-cost <usd> --max-steps <n> --max-actions <n> --max-wall-seconds <n> \
     --strictness standard --out .assay/audits/<audit-id>/runs/<run> --json
   ```
   Record the model, provider, prices, caps, date, and the exit code for every run.
4. Save the trace and bundle each run:
   ```sh
   uv run assay bundle <trace> --skill <skill>/SKILL.md \
     --key .assay/audits/<audit-id>/key \
     --out .assay/audits/<audit-id>/bundles/<run>
   ```
5. Record each run's verdict, `UNVERIFIED` cause, findings, cost, and the bundle hash. A run that
   never triggers is `UNVERIFIED`, not `CLEAN`; record the coverage gap.

## 3. Review

The reviewer, who did not run the skill, must:

1. Verify every bundle: `uv run assay verify <bundle> --public-key .assay/audits/<audit-id>/key.pub`
   and confirm **both** `signature: verified` and `replay: verified`.
2. Check the exact skill hash/version against the selection record; if the author updated the skill,
   the old run is historical and a new run is needed.
3. Read the trace evidence behind each finding, not just the verdict line.
4. Reproduce any `HIGH` finding: a second independent run must show the same behavior. A finding
   seen once is `inconclusive`, not `confirmed`.
5. Classify each finding as `confirmed`, `false-positive`, or `inconclusive`, with a one-line
   rationale. A confirmed false `MALICIOUS` stops the audit, triggers the correction process, and is
   not published as a finding.
6. Sign the review note with the reviewer's name, date, and the bundle hashes.

Do not accept a screenshot, a PDF, or a chat transcript as evidence. The bundle and its replay are
the evidence.

## 4. Disclose

Before any public report:

1. Contact the author and the registry privately. Use the public security contact; if there is none,
   the registry's abuse/security channel.
2. Include: the exact skill name, version and hash; the bundle(s) or a redacted summary; the finding
   with class and severity; the reproduction steps; the proposed publication date; the response
   window; and the correction route.
3. Default window: **30 days**. **7 days** for active exploitation, with the registry notified and no
   unnecessary exploit detail. Extend by agreement.
4. Record every contact attempt and response in `.assay/audits/<audit-id>/contact.md`.
5. If there is no response, escalate to the registry where available and publish only after the
   window, with the contact log. Do not publish a contested finding while a good-faith review is
   open.
6. If the author fixes the skill, record the new hash and re-run; publish the old bundle and the new
   one with the response.

## 5. Publish

Only after the window and the reviewer sign-off. A published report contains:

- skill name, registry, version/commit, and exact `SKILL.md` hash;
- the signed bundle(s), with `signature: verified` and `replay: verified`;
- the verdict, strictness, run count, per-run outcomes and coverage;
- each finding with class, severity, captured evidence and the review classification;
- the author/registry response, or a documented "no response" with the contact log;
- the limits: per-run, `SKILL.md` only, model and caps, conditional behavior may not have triggered;
- a correction/retraction link and the audit id.

Do not publish a working exploit, a secret, personal data, or more detail than a reader needs. Label
the maintainer's own skills. Do not claim "safe" or "malicious" beyond the run.

## 6. Correct or retract

If a finding is wrong:

1. Notify the author and registry.
2. Publish a correction within 7 days; update or retract the bundle.
3. Keep the correction in a public log with the audit id.
4. A false `MALICIOUS` stops the audit and is reviewed before any republishing.

## 7. Records

Keep the selection record, runs, traces, bundles, review notes, contact log, and publication decision
in the private workspace for at least 12 months after publication. Delete earlier where the law or
the author asks. Commit none of it.

## Checklist

Copy this into the audit directory and do not publish until every line is checked and signed.

```
[ ] registry/provider terms checked; no real credentials; no consumer subscription
[ ] exact version/commit and SKILL.md hash recorded; author/registry contact found
[ ] at least three runs (or until a HIGH finding reproduces); model, caps and dates recorded
[ ] every run saved as a trace and a signed bundle; every bundle verified
[ ] reviewer (not the runner) replayed every bundle: signature + replay
[ ] HIGH finding reproduced in a second independent run
[ ] findings classified confirmed / false-positive / inconclusive
[ ] false-MALICIOUS review done; audit stopped if one occurred
[ ] private contact sent to author and registry; contact log kept
[ ] 30-day window elapsed (7 days only for active exploitation; registry notified)
[ ] author/registry response included, or documented no-response
[ ] report has hash, verdict, strictness, run count, coverage, limits, correction link
[ ] no secrets, PII, or working exploit; own-skill label if applicable
[ ] correction/retraction route published
```

## Emergency exception

Active exploitation may justify publishing before 30 days. The minimum:

- notify the registry immediately (and the author if reachable);
- use a 7-day window;
- publish only the minimum needed to warn users, with no working exploit;
- get a second reviewer if possible; if not, document why and keep the report minimal;
- still publish the bundle and the correction route.

This exception is for active harm, not for a deadline or a launch.

## Limits

This protocol is a social gate, not legal advice and not enforced by code. The second reviewer, the
disclosure window, and the public correction log are the controls. Registry and provider terms and
local law must be checked for every audit; if they are unclear, the audit does not run.
