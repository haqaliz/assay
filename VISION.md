# Assay: Vision

> A skill's markdown tells you what it claims. Only running it tells you what it does.

---

## The bet in one sentence

The valuable, defensible problem in agent-skill security is not *reading* a skill and guessing
whether it's dangerous — a pattern scanner can do that, badly, because the most dangerous
instructions are plain English with no code to scan. It is **running the skill for real, in a
sandbox, against a real agent, and proving what it actually did against what it claims to do.**
Assay is the harness that does that, for any skill format.

---

## Why now

- **The ecosystem exploded faster than its security did.** skills.sh went from a single feature
  to ~670,000 listed skills in under nine months; daily submissions to registries jumped from
  under 50/day to over 500/day in two weeks (Jan–Feb 2026).
- **Real attacks already happened at scale.** The ClawHavoc campaign planted 1,184+ malicious
  skills on ClawHub; 5 of the top 7 most-downloaded skills at peak infection were malware.
  Publishing required only a `SKILL.md` and a week-old GitHub account — no signing, no review,
  no default sandbox.
- **Static scanning measurably misses the attack.** A skill's malicious instruction can be plain
  English in the prose, not code. A metadata-only attack biased agent selection 77.6% of the time
  and evaded governance classifiers in up to 100% of cases. The only reliable signal is observing
  what the skill actually makes the agent do.
- **A standard is forming industry-wide, with no enforcement layer yet.** `SKILL.md` crossed from
  one vendor's feature to a cross-platform format in under a year. Whoever builds the trusted
  verification layer for that format early becomes infrastructure.

---

## The founder's unfair advantage

The moat is **engineering**: sandbox isolation, real-agent-driven behavior capture, declared-vs-
observed diffing, and a compounding findings corpus. That is exactly a full-stack developer + ML
engineer's edge, and it's the same discipline already proven in Belay (agent-trace verification)
and Plumb (execution-grounded claim verification). Assay needs no proprietary dataset or
credential the founder lacks.

---

## Why it's defensible ("gets better as models improve")

The durable core is the sandbox + the observed-behavior capture + the accumulating corpus of
labeled findings. A stronger model, used as the sandboxed agent, surfaces a skill's real behavior
more completely and triggers more of its conditional logic — making Assay's observations
*sharper*, never redundant. A pattern scanner gets cheaper to fool as attacks get more
sophisticated; a captured, reproduced behavior does not.

---

## Positioning

- **Not a static scanner.** We do not treat "looks safe" as a verdict. SkillSpector-style static
  analysis is a useful, cheap pre-filter — it is not the thing we sell.
- **Not an antivirus signature database.** We don't match known malware hashes; we observe what
  a skill does when it actually runs, including novel attacks nobody has signatured yet.
- **The verdict is honest:** `CLEAN` / `FLAGGED` / `MALICIOUS` / `UNVERIFIED`, and `UNVERIFIED` is
  never dressed up as `CLEAN`. `MALICIOUS` requires a reproduced, captured behavior — never an
  accusation based on how a skill's text reads.

---

## The wedge → the company

1. **OSS on-ramp:** a CLI that sandboxes any skill, runs it against a real (BYOK) agent, and
   returns a verdict with a replayable record. Free, self-hostable. Earn credibility by
   publishing a real audit of widely-used public skills, with responsible disclosure.
2. **Team / registry layer:** the findings corpus as a shared, queryable asset; a registry
   (ClawHub-style or your own) that checks a skill before letting it list, using the same engine.
3. **Hosted layer:** a managed scanning/signing service that skill registries and enterprise
   agent deployments run every install through (BYOK, opt-in) — the business.

---

## Non-goals

- Guessing maliciousness from a static read of a skill's text, dressed up as verification.
- Matching known-malware signatures as the primary mechanism (useful as a pre-filter only).
- Running a skill against real secrets, real user data, or an unsandboxed environment.
- Automating against a consumer chat subscription instead of a BYOK API key (open question,
  not a design assumption — likely against most providers' terms).
- Any design where a better base model would make Assay's observed-behavior verdict redundant.

---

## The one-line mantra

**Run the skill. Watch what it actually does. Check that against what it claims.**
