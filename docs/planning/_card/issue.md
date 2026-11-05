# feat a5-calibration — held-out shell calibration

## Brief

Calibrate A5's shell pattern list on a **held-out** set, without changing the verdict contract or the
floor. Add `corpus/heldout/` with 8 synthetic cases (4 malicious, 4 clean guards), measure the
baseline with the current patterns, then add four high-confidence `HIGH` shell patterns (`dd` to a
device, `pty.spawn`, `/dev/tcp/`, `socat ... EXEC:/bin/sh`) and re-measure. Target: 4/4 malicious
`MALICIOUS` after (0/4 before, all `FLAGGED`), 4/4 clean `CLEAN` before and after, 0 false
`MALICIOUS`. The main 20-case corpus metrics must not move. No instruction/network severity change;
no new dependency.

Source: the A7 PRD's "A5 frozen in this PR; tuning is a follow-up with a held-out set" and the A5
row's "deliberately narrow, measured by A7, not yet tuned." The main corpus report (precision 1.00
5/5, recall 0.71 5/7, false-MALICIOUS 0/6) does not show a shell defect; the held-out set targets
common shell patterns the narrow list misses.

## Context carried from the pick

- `SHELL_PATTERNS` in `src/assay/verdict/assess.py` are deliberately short; a captured command
  matching one is `SHELL/HIGH` and can make `MALICIOUS` (with `review_required`).
- The A7 corpus is the development set; it must not be tuned on. A separate held-out set is the
  calibration control.
- The verdict contract: `MALICIOUS` needs a captured `HIGH` finding; instruction matches are capped
  at `REVIEW`; network divergences are `REVIEW`; the floor cannot be lowered. This slice only adds
  shell patterns; no severity/verdict change.
- The main corpus has no `dd`, `pty.spawn`, `/dev/tcp/`, or `socat` commands; the new patterns
  should not change its metrics.
- No new dependency; synthetic traces, no model/network.
