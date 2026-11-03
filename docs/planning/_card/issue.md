# feat bundle-replay — self-proving signed bundles (A6 follow-on)

## Brief

Close the A6 replay gap. A bundle schema 2 carries the exact `SKILL.md` source alongside the trace
and assessment. `assay verify` re-parses that source, re-runs the shipped `assess` at the recorded
strictness, and refuses unless the re-derived assessment equals the stored one. A valid signature
over a false verdict now fails with `replay-mismatch`; the signature proves who attested the record,
and the replay proves the verdict follows from the recorded inputs. The trace stays schema 2 and the
corpus is unaffected. `assay bundle` embeds the source (capped by `MAX_SKILL_BYTES`); schema-1
bundles are refused by name; no new dependency and no A5 changes.

Source: the A6 PRD's O1 and `docs/technical/ARCHITECTURE.md` "Verdict replay" open question, both of
which name this as the first follow-on. A6 and A7 shipped (PRs #9 and #10). Selected 2026-11-03.

## Context carried from the pick

- `src/assay/bundle/` holds the canonical record and the `ssh-keygen` adapter; `verify` today checks
  the signature and the hash list only (`src/assay/bundle/build.py`).
- `src/assay/ingest/claude.py` parses `SKILL.md` from a path and hashes the raw bytes; there is no
  text entry point yet.
- `assess(skill, trace, policy)` needs the declared `Scope`, the body/description for instruction
  findings, and the skill hash; the trace carries none of those.
- The corpus (`corpus/`) has 20 schema-2 traces; this slice must not require regenerating them.
- Constraints: no execution of the embedded source; no A5 changes; no over-claim beyond `SKILL.md`.
