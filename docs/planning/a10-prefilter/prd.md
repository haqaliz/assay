# PRD — `a10-prefilter` (A10: optional static pre-filter)

Status: approved 2026-11-05 (next milestone). Date: 2026-11-05.
Pipeline position: A10, the last engine capability. No verdict, no run.

## Problem statement

A user with a directory of skills has to choose what to run; every `assay check` costs tokens and
time. A cheap static pass can order that work, but the project's whole thesis is that a static read
is not a verdict. The pre-filter must be useful for prioritization and **structurally incapable** of
being mistaken for a decision: no `CLEAN`/`FLAGGED`/`MALICIOUS`, no `Assessment`, no trace, no
`verdict` field. It may say "look here first", never "this is safe/unsafe".

For whom: a user triaging a skill collection; a reviewer deciding what to run next; the future
registry/CI queue.

## Goals and success metrics

| Goal | Metric |
|---|---|
| Cheap triage exists | `assay triage <skill>` parses the skill and prints `priority` + `signals`; no model, network, sandbox or trace |
| It cannot be a verdict | The JSON has no `verdict`, `cause`, `findings`, `blocked` or trace; the module does not construct an `Assessment` |
| It orders the work | High-signal text (credentials, persistence, remote-script, destructive, prompt injection) → `high`; medium (network, shell, filesystem, install) → `medium`; none → `low` |
| It is honest | The output and docs say "pre-filter only; run `assay check` for a verdict"; a low priority is not "safe" |
| No collateral change | `check`/`bundle`/`verify`/`corpus` outputs and exit codes are unchanged; A5/corpus untouched; no new dependency |

## Users and scenarios

1. **User with 50 skills** — `assay triage` each, run the high/medium first.
2. **Reviewer** — sees why a skill was prioritized; the signals are labels, not findings.
3. **Registry/CI** — uses priority to order a queue, never as a gate.

## Requirements

### Must have

1. **Triage module** (`src/assay/triage/`):
   - `Priority(StrEnum)`: `low`, `medium`, `high`.
   - `Triage` frozen record: `priority: Priority`, `signals: tuple[str, ...]` (sorted unique), no
     verdict/finding/trace fields.
   - `triage(skill: Skill) -> Triage`: apply a fixed static pattern list to the skill's
     description + body (case-insensitive), collect the signal labels, set priority to the maximum
     of the matched signal priorities (low if none).
   - Patterns (labels and priorities; exact regexes in the spec):
     - high: `remote-script` (`curl|wget ... | sh`), `credentials` (api key/secret/token/password/
       `.env`/`id_rsa`/`authorized_keys`/`ssh`), `persistence` (`crontab`/`launchctl`/`systemd`/
       `systemctl`/`rc.local`), `prompt-injection` (ignore previous/system prompt/exfiltrate/do not
       tell/override your), `destructive` (`rm -rf`, `dd ... of=/dev/`, `mkfs`), `privilege`
       (`sudo`, `chmod 777`);
     - medium: `network` (URL/curl/wget/fetch/requests/httpx/socket), `shell` (bash/sh/zsh/exec/
       eval/system/subprocess/os.system/child_process), `filesystem` (`/etc/`, `/usr/`, `/bin/`,
       `~/`, `.ssh/`, `.aws/`, `.config/`), `install` (npm/pnpm/yarn/pip/uv/brew/apt/go install/add/
       get);
     - the signal list is deliberately small and static; it is not a detection list.
2. **CLI** `assay triage <skill> [--json]`:
   - `<skill>` may be a `SKILL.md`, `.mdc`, or a directory (append `SKILL.md`), using `parse_skill`.
   - Human output: `skill: <name> <hash12>`, `format: <format>`, `priority: LOW|MEDIUM|HIGH`,
     `signals: <comma list or none>`, `note: pre-filter only; this is not a verdict. Run assay check.`,
     `exit: 0`.
   - JSON (canonical): `{"schema":1,"skill":{"name","content_hash","path","format"},"priority",
     "signals":[...],"note":"..."}`. **No `verdict`, `cause`, `findings`, `blocked`, `trace` or
     `cost`.**
   - Exit `0` for a computed triage (any priority), `1` for a parse refusal with a `triage`
     envelope (`schema`, `skill`, `cause`, `detail`; no verdict), `2` usage, `130` Ctrl-C.
   - No model/sandbox/network/trace; no file writes.
3. **Guardrail tests.** The JSON key set is exactly the triage shape; no `verdict` key; the module
   does not import/construct `Assessment`; a high-signal skill is `high`, a benign one `low`, a
   medium one `medium`; the CLI never calls a model/sandbox (sentinels not needed; the command has no
   seam).
4. **Docs/status.** README usage + "not a verdict"; ARCHITECTURE A10 module/CLI and guardrail;
   CAPABILITY_ROADMAP A10 built; ROADMAP progress; CLAUDE.md status. The A10 is optional and is not
   the moat; say it.
5. **No A5/corpus/trace/bundle change; no new dependency.**

### Should have

6. The signal labels are readable and stable; the human/JSON output is deterministic.
7. A parse refusal uses a `triage` envelope and no verdict.
8. A test that a low-priority benign skill still says "not a verdict".

### Nice to have (deferred)

Batch triage of a directory; a priority threshold for `check`; a queue/registry integration; model
assistance; replacing the static list with a learned ranker. None is A10's verdict.

## Technical considerations

- **Structural guardrail.** The triage module does not import `assay.verdict` and the CLI has a
  separate renderer; there is no `Assessment` in the path. The JSON has no verdict field. This is
  stronger than "returns UNVERIFIED": it cannot be quoted as a verdict at all.
- **Static text only.** The scan is on the parsed skill's description + body, not on captured
  behavior. It is a candidate-ordering heuristic; the docs and output say so.
- **Why these signals.** They are cheap, common, and easy to explain; they are not calibrated and
  must not be treated as findings. The A7 corpus is not used to tune them.
- **No run.** No model, no sandbox, no network, no trace; the command is deterministic.
- **No new dependency.**

## Risks and open questions

| Risk | L/I | Mitigation |
|---|---|---|
| A user quotes a priority as a verdict | High/High | No verdict field; output says "not a verdict"; docs; a test pins the key set |
| A static scan is easy to fool | High/Med | Say it; it orders runs, it does not decide; the sandbox is the verdict |
| False high/low priority | Med/Med | It is a queue heuristic; no accuracy claim; labels are visible |
| The A10 distracts from the audit/moat | Med/Med | Keep it small; docs say optional; the audit remains the credibility play |
| The signal list becomes a de facto detector | Med/Med | Fixed list, no corpus tuning, no severity/finding vocabulary |

Open questions (recommendations):

- **O1 — why not return `UNVERIFIED`?** [No verdict at all is stronger and avoids the A5 cause
  vocabulary; the A10 row allows "never above UNVERIFIED", and none is better.]
- **O2 — batch mode?** [Defer; one skill per invocation.]
- **O3 — a `--min-priority` for `check`?** [Defer; the user chooses what to run.]
- **O4 — tune the list?** [No; it is a static heuristic, not the benchmark.]

Challenge: **does a static pre-filter undermine the "execution decides" thesis?** Only if it is
mistaken for a verdict. This slice makes that mistake structurally hard: no verdict, no findings, no
trace, and a note in every output. The docs keep it optional and secondary.

## Out of scope

- Any verdict, finding, severity, cause or `Assessment`.
- Model/sandbox/network/trace/cost; a run.
- Tuning on the corpus; a learned ranker; batch/queue/registry.
- A5, corpus, bundle, trace or format changes.

## Areas to strengthen before sharing (self-critique)

- 🔴 **Optional and not the moat.** A10 is a queue heuristic; the execution-grounded verdict is the
  product. Do not let the docs imply otherwise.
- 🟡 **The static list is uncalibrated.** It is a heuristic; no precision/recall claim.
- 🟡 **A low priority is not safe.** The note says so; the docs repeat it.
- 🟡 **A high priority is not malicious.** The signals are candidates, not findings.
- Question before greenlighting: **should the command be named `triage` or `prefilter`?** [`triage`
  reads as ordering; `prefilter` is the A10 term. Use `triage` in the CLI and "static pre-filter" in
  the docs.]
