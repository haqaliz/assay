# feat real-corpus — M2.3 prep: private real-world control set

## Brief

Add a **private real-world control set** of the remaining eight Plumb skills, run once each against
the local model, stored as `local-model` cases under `corpus/real/`. The labels are `clean` (the
maintainer's own benign skills) and the purpose is to measure coverage and false positives on real
instructions, not to benchmark detection or publish findings. The 20-case development corpus and the
A5 calibration set stay unchanged; the real set is reported separately. No third-party skills, no
publication, no audit claim, no code change beyond a loader test and docs.

Source: the A7 corpus limit ("18 synthetic, 2 local-model; synthetic-dominated"), the M2.3 audit
gate (no third-party audit until a second reviewer), and the A7 PRD's "grow with real cases." This
is the safe, own-skill step before any public audit.

## Context carried from the pick

- `corpus/` is the 20-case development benchmark; `corpus/heldout/` is the 8-case A5 calibration
  control. Both are unchanged by this unit.
- The existing local-model cases are `plumb-report-desktop-write` and
  `plumb-begin-fast-no-trigger`, stored from the 2026-11-03/05 runs.
- Ollama `qwen3-coder:30b` is available locally; runs cost nothing (`--input-price 0
  --output-price 0 --max-cost 0.01`).
- The M2.3 protocol requires three runs and a second reviewer for an audit; this set is a **control
  corpus**, not an audit, and makes no public claim.
- Constraints: no real secrets; the sandbox runs every tool call; no publication; no A5 change.
