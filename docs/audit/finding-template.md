# Finding template

Copy this into `.assay/audits/<audit-id>/finding.md` and keep it private until the disclosure window
has passed. Replace every placeholder; delete a section only if it does not apply.

---

# Finding — <audit-id> — <skill name>

**Status:** `private | disclosed | published | corrected | retracted`
**Audit id:** `<YYYY-MM-DD>-<skill-slug>`
**Runner:** `<name>`  **Reviewer:** `<name, must not be the runner>`  **Publisher:** `<name>`
**Dates:** selected `<YYYY-MM-DD>`, first run `<YYYY-MM-DD>`, contacted `<YYYY-MM-DD>`,
published `<YYYY-MM-DD>`

## Skill

- **Registry / URL:** `<url>`
- **Version / commit:** `<tag or commit>`
- **`SKILL.md` hash:** `<64 hex>`
- **Author / registry contact:** `<public contact>`
- **License / terms checked:** `<license>`, checked `<YYYY-MM-DD>`; `<notes>`
- **Own skill?** `<yes/no>` — if yes, say so in the published report.

## Runs

| Run | Date | Model / provider | Strictness | Caps | Verdict | Cause | Bundle hash |
|---|---|---|---|---|---|---|---|
| 1 | | | standard | | | | |
| 2 | | | standard | | | | |
| 3 | | | standard | | | | |

- **Coverage:** `<decided / total>`; `<UNVERIFIED causes>`
- **Model limits:** `<what the model did not trigger>`

## Findings

### `<finding label>`

- **Class:** `<undeclared-file | undeclared-network | shell | instructions>`
- **Severity:** `<low | review | high>`
- **Captured action:** `<target>`, outcome `<ok | denied | failed>`
- **Evidence:** `<trace event / bundle path>`, run `<n>`
- **Reproduction:** `<second independent run / trace replay>` — `<result>`
- **Classification:** `<confirmed | false-positive | inconclusive>` — `<rationale>`
- **Limits:** `<what this does not prove>`

## Disclosure

- **Contact attempts:** `<date, channel, recipient, message id>`
- **Window:** `<30 days | 7 days emergency | extended by agreement>` — ends `<YYYY-MM-DD>`
- **Author response:** `<summary or "no response">`
- **Registry escalation:** `<date / reference / none>`
- **Publication decision:** `<publish / hold / correct / retract>` — `<reason>`
- **Reviewer sign-off:** `<name, date, bundle hashes>`

## Publication draft

> **<skill name> — <verdict> on <date>**
>
> Assay ran `<skill>` version `<commit>` (`SKILL.md` hash `<hash>`) `<n>` times with `<model>` at
> `standard` strictness. The signed bundle(s): `<links/hashes>`. Result: `<verdict>`; coverage
> `<decided/total>`; `UNVERIFIED` causes: `<causes>`.
>
> Finding: `<one paragraph, evidence and reproduction, no working exploit>`.
>
> Author/registry response: `<summary or "no response after documented contact">`.
>
> Limits: this is a per-run result on this model and this skill version. It is not a claim that the
> skill is safe or malicious in general, and it covers `SKILL.md` only, not the rest of the skill
> directory. Replay the bundle with `assay verify` and the published public key.
>
> Correction/retraction: `<link or audit id>`.

## Corrections

- `<date>` — `<what changed, why, link>`
- `<date>` — `<retraction, if any>`
