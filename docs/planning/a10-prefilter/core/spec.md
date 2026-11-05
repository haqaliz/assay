# Spec — `a10-prefilter` / `core` (A10 static pre-filter)

## Problem slice & user outcome

`assay triage <skill>` parses a skill and prints a deterministic `priority` (`low`/`medium`/`high`)
and the static `signals` that produced it. It has no verdict, no findings, no trace, and no run; the
output says "pre-filter only; run `assay check`". The user can order a collection without mistaking
the order for a decision.

## In scope

- `src/assay/triage/` (`Priority`, `Triage`, `SIGNALS`, `triage`).
- `assay triage <skill> [--json]` + a `triage` refusal envelope.
- Tests for the signal table, the no-verdict guardrail, and the CLI.
- Docs/status: README, ARCHITECTURE, CAPABILITY_ROADMAP A10, ROADMAP, CLAUDE.md.
- No A5/corpus/trace/bundle change; no new dependency.

## Out of scope

Any verdict/finding/severity/cause/`Assessment`; model/sandbox/network/trace/cost; a run; batch,
queue, registry, learned ranker; tuning on the corpus; A5 changes.

## Data model

```python
class Priority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

@dataclass(frozen=True, slots=True)
class Triage:
    priority: Priority
    signals: tuple[str, ...]   # sorted unique labels; no verdict/finding/trace fields

def triage(skill: Skill) -> Triage
```

- Scan `f"{skill.description}\n{skill.body}"` with the fixed patterns (case-insensitive).
- Collect labels; priority = max of matched priorities (`HIGH` > `MEDIUM` > `LOW`); no match → `LOW`.
- `signals` sorted unique; deterministic; no I/O.

## Signals (labels, priority, regex)

| label | priority | regex |
|---|---|---|
| `remote-script` | high | `\b(?:curl|wget)\b[^\n]*\|\s*(?:sudo\s+)?(?:ba|z)?sh\b` |
| `credentials` | high | `\b(?:api[_-]?key|secret|token|password|passwd|\.env|id_rsa|authorized_keys|ssh)\b` |
| `persistence` | high | `\b(?:crontab|launchctl|systemd|systemctl|rc\.local|autostart)\b` |
| `prompt-injection` | high | `\b(?:ignore\s+(?:all\s+)?previous|system\s+prompt|exfiltrat|do\s+not\s+tell|without\s+telling|override\s+your)\b` |
| `destructive` | high | `\brm\s+-rf\b|\bdd\b[^\n]*\bof=/dev/|\bmkfs\b` |
| `privilege` | high | `\bsudo\b|\bchmod\s+777\b` |
| `network` | medium | `\b(?:https?://|curl|wget|fetch|requests\.|httpx|socket)\b` |
| `shell` | medium | `\b(?:bash|sh|zsh|fish|exec|eval|system|subprocess|os\.system|child_process)\b` |
| `filesystem` | medium | `(?:/etc/|/usr/|/bin/|/private/|~/|\.ssh/|\.aws/|\.config/)` |
| `install` | medium | `\b(?:npm|pnpm|yarn|pip|pip3|uv|brew|apt|apt-get|go)\s+(?:install|add|get)\b` |

- The list is fixed and static; it is not a detection list and is not tuned on the corpus.
- A high signal is not `MALICIOUS`; a low priority is not safe.

## CLI

`assay triage <skill> [--json]`:
- `<skill>` may be a `SKILL.md`, `.mdc`, or a directory (append `SKILL.md`); `parse_skill`.
- Human:
  ```
  skill: <name> <hash12>
  format: <format>
  priority: HIGH
  signals: credentials, network, shell
  note: pre-filter only; this is not a verdict. Run `assay check`.
  exit: 0
  ```
  `signals: none` when empty; priority uppercase.
- JSON canonical:
  `{"schema":1,"skill":{"name","content_hash","path","format"},"priority","signals":[...],"note":"..."}`
  — **no `verdict`, `cause`, `findings`, `blocked`, `trace`, `cost`**.
- Parse refusal: a `triage` envelope `{schema:1, skill:{path}, cause, detail}` (no verdict), exit 1.
- Exit `0` for a triage, `2` usage, `130` Ctrl-C; no model/sandbox/network/trace; no file writes.

## Acceptance criteria

1. `triage(skill)` returns the expected priority/signals for a high-signal skill, a medium one and a
   benign one; signals are sorted unique; the scan is case-insensitive.
2. The `Triage` record and module have no verdict/finding/trace fields and do not construct an
   `Assessment`; the JSON key set is exactly the triage shape (a test asserts `"verdict" not in
   payload`).
3. `assay triage` on a high-signal skill exits 0, prints the human shape, and `--json` is canonical;
   a benign skill prints `priority: LOW`, `signals: none`; a parse failure exits 1 with the triage
   envelope and no traceback.
4. The command writes no files and calls no model/sandbox/network; the existing `check`/`bundle`/
   `verify`/`corpus` outputs and exits are unchanged.
5. Docs: README usage + "not a verdict"; ARCHITECTURE A10 module/CLI and guardrail; CAPABILITY_ROADMAP
   A10 built; ROADMAP progress; CLAUDE.md status. The docs say A10 is optional, uncalibrated, and not
   the moat.
6. `uv run pytest` green and offline; no new dependency; no A5/corpus/trace/bundle change.

## Dependencies & sequencing

A1 (`parse_skill`), the CLI/output conventions. No A5/A6/A7 dependency. Order: module → CLI → tests →
docs.

## Risks

- A priority is a queue heuristic, not a verdict; the output/docs say so.
- Static text is easy to fool; no accuracy claim; the sandbox is the verdict.
- The signal list is uncalibrated and fixed; not tuned on the corpus.
- A10 is optional and not the moat; keep it small.
