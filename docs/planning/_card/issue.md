# feat a10-prefilter — optional static pre-filter (A10)

## Brief

Add `assay triage <skill>`: a cheap, deterministic static pre-filter that ranks a skill's text for
which run to prioritize. It emits **priority** (`low`/`medium`/`high`) and **signals** only. It
never emits `CLEAN`/`FLAGGED`/`MALICIOUS`, has no `verdict` field, no `Assessment`, and never calls a
model or the sandbox. The output says "pre-filter only; run `assay check` for a verdict." This is
A10: it may order the work, never decide it.

Source: `docs/technical/CAPABILITY_ROADMAP.md` A10 ("Optional static pre-filter. Cheap triage that
can prioritize runs but never assigns a verdict above UNVERIFIED") and `CLAUDE.md` constraint 1
("A static scan or a model reading the skill's markdown may flag a candidate or triage priority. Only
an actual sandboxed run ... may produce a verdict above UNVERIFIED"). A1–A8 are shipped; A9 is
deferred; A10 is the last buildable engine capability.

## Context carried from the pick

- The engine has a deterministic `parse_skill` (Claude/OpenClaw/Cursor) and a canonical CLI/output
  style; `check` is the only path that produces an `Assessment`.
- The static pre-filter must be structurally unable to be mistaken for a verdict: no `verdict` key,
  no `UnverifiedCause`, no `findings`, no trace.
- The A7 corpus is a benchmark; the A10 is not measured by it and must not change it.
- No new dependency; no network/model/sandbox.
