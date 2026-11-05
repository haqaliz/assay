# feat instruction-calibration — held-out instruction calibration

## Brief

Calibrate A5's **instruction** patterns on a fresh held-out set, without changing the verdict
contract or the `REVIEW` cap. Add `corpus/heldout-instructions/` with 8 cases: four malicious
instruction texts the current list misses, and four clean near-miss guards, two of which the current
broad `system prompt`/`override your` patterns wrongly flag. Measure the baseline, add four
high-confidence patterns, narrow the two broad ones, and re-measure. Target: malicious detection
0/4 → 4/4 (`FLAGGED`, never `MALICIOUS`), clean reviews 2/4 → 0/4, no false `MALICIOUS`, and the
20-case benchmark unchanged.

Source: the A5 row ("the instruction list remains narrow") and the A7 PRD's held-out-calibration
discipline. The shell list was calibrated in #16; this is the other half. The instruction cap at
`REVIEW` is deliberate and unchanged.

## Context carried from the pick

- `INSTRUCTION_PATTERNS` in `src/assay/verdict/assess.py` is short; `system prompt` and
  `override your` are broad and can flag benign documentation/preferences.
- Instruction findings are capped at `REVIEW` and can never produce `MALICIOUS`; the held-out target
  is detection/clean-review, not strict recall.
- The main 20-case benchmark has one instruction case (`ignore previous instructions`) and no
  near-miss guards; the A5 shell calibration set is separate and unchanged.
- No model/network; synthetic traces; no new dependency.
