# PRD — `behavior-capture` (A4: behavior capture and diff)

Status: draft for review. Date: 2026-10-29.
Pipeline position: A4 of `docs/technical/CAPABILITY_ROADMAP.md`; depends on A1, A2 and A3 (all
merged). Completes the data half of the Phase 0 gate.

## Problem statement

A3 produces a `RunOutcome` in memory and drops it when the process exits. Nothing persists what the
skill did, nothing compares it to `Skill.scope`, and a verdict therefore cannot be re-derived without
paying for another non-deterministic run. Assay's promise is a *replayable record*; today there is no
record.

For whom: A5 (the verdict), A6 (the signed bundle), A7 (the corpus), and a human reviewer who wants
to see why a run was flagged. None of them can be built on a live `RunOutcome`.

## Goals and success metrics

| Goal | Metric |
|---|---|
| Every action becomes a typed event | A 4-action run yields 4 tool events plus 2 instruction events, in order, each with a kind, target, outcome and content hash |
| The record is content-addressed and replayable | `Trace.hash` is stable across two captures of identical inputs and changes when one event changes; `TraceStore` names the file by that hash and refuses a tampered file |
| Diff preserves A1's tri-state | For each dimension, a matrix test asserts `None` → `UNDECLARED`, `()` → `EXCEEDED`, and a matching declaration → no divergence |
| The four floor classes are represented | file read, file write, network and shell events all appear; instruction events carry the exact text delivered as system/user instructions |
| No re-run, no model call, no sandbox | `diff(skill, trace)` reads only the trace; the capture suite runs offline |
| No verdict leaks in | The module contains no `CLEAN`/`FLAGGED`/`MALICIOUS` string and no severity, threshold or exit code |

Not a goal: deciding whether the skill is safe, signing the trace, or building a corpus.

## Users and scenarios

1. **A5** — maps `Diff.divergences` to findings and applies strictness; needs `EXCEEDED` and
   `UNDECLARED` to stay distinct, or a skill with no declarations is wrongly called malicious.
2. **The Phase 0 gate run** — capture a real Plumb skill run, diff it, and look at the first observed
   behavior that its `SKILL.md` never declared.
3. **A reviewer** — opens the trace JSON and sees the command, the URL, the path, the output excerpt
   and any sandbox denials, without trusting a re-run.
4. **A6 later** — hashes the trace file into the bundle; the trace must be canonical bytes.

## Requirements

### Must have

1. **Event model** (frozen): `Event(kind, outcome, target, input_sha256, request, content_sha256,
   content_bytes, excerpt, denials, truncated)` where
   - `kind ∈ {FILE_READ, FILE_WRITE, NETWORK, SHELL, INSTRUCTION, TOOL}`,
   - `outcome ∈ {OK, DENIED, FAILED}`,
   - `target` is the normalised path, `host:port`, the shell command, `"system"`/`"user"` for
     instructions, or the tool name for an unknown tool,
   - `input_sha256` covers the model-supplied payload (`write_file` content) and is `None` when the
     argument is absent or not a string,
   - `request` is the raw URL for a network event (the `target` is only `host:port`, so a secret in a
     query string must still be in the trace) and `None` elsewhere,
   - `content_sha256`/`content_bytes` cover `RunRecord.stdout + stderr` when a record exists (what
     the model saw), or the tool's own output when the action never reached the sandbox,
   - `excerpt` is the first 4 KB of that content, `denials` are `"kind: detail"` strings,
   - `truncated` mirrors the sandbox's output-cap flag.
2. **`capture(skill, task, outcome) -> Trace`** maps each `ToolAction` to exactly one event:
   `read_file`→FILE_READ, `write_file`→FILE_WRITE, `http_get`→NETWORK, `run_shell`→SHELL, unknown
   tool→TOOL. Two INSTRUCTION events are always appended (`system` = `skill.body`, `user` = `task`).
   An action with a `RunRecord` carries its denials; a `DENIED` action is still an event (an attempt
   is evidence). Instruction events are appended only when at least one model call happened
   (`steps > 0`): a run refused for a missing key never delivered those instructions.
   No timestamps, so the trace is deterministic.
3. **Trace record** (frozen): `schema` (integer), `skill_name`, `skill_content_hash`, `task_sha256`,
   `cause` (the A3 stop cause value or `None`), `input_tokens`, `output_tokens`, `cost_usd`, and
   `events`. `trace.hash` is `sha256` of canonical JSON (`sort_keys`, compact separators,
   `ensure_ascii=False`), bare lowercase hex.
4. **`TraceStore(root)`**: `save(trace) -> Path` writes `<hash>.json` atomically and returns the path;
   `load(path) -> Trace` re-parses, recomputes the hash and raises `TraceIntegrityError` on a
   mismatch. `root` is created if missing.
5. **`diff(skill, trace) -> Diff`**:
   - `Divergence(kind, target, status, outcome, reason, denials)` with
     `status ∈ {EXCEEDED, UNDECLARED}`; the event's outcome travels with the divergence so A5 can
     say "attempted" rather than "did".
   - `Coverage(dimension, declared, events)` for files, network, shell and instructions; `declared`
     means the corresponding scope key exists (instructions have no scope key, so `False`).
   - `Diff` also carries `skill_content_hash` and `trace_hash`, and `diff` **refuses** a trace whose
     skill hash does not match the skill (`CaptureError`). Without that binding a mismatched pair
     silently hides a real divergence.
   - Files: normalise the target with `posixpath.normpath` (so `out/../../etc/passwd` becomes
     `../etc/passwd` and cannot match `out/*`), make a path under the action's run root relative,
     resolve a live run-root path so a symlink that leaves the root is recorded as its real target,
     then match declared patterns with `fnmatch`; `None` → `UNDECLARED`, `()` → `EXCEEDED`, no match
     → `EXCEEDED`. Applies to reads and writes.
   - Network: derive canonical `host:port` from the URL (lowercase, trailing dot removed, IPs
     compressed, default 443 for https and 80 for http, explicit port respected); declared entries
     are normalised the same way and a missing port means 443. Exact match only. `None` →
     `UNDECLARED`, `()` → `EXCEEDED`, no match → `EXCEEDED`.
   - Shell: within scope only if `scope.tools` contains `Bash` or an entry starting with `Bash(`.
     `None` → `UNDECLARED`, otherwise a missing Bash entry → `EXCEEDED`.
   - Instructions: never a divergence in A4 and not reported as declared scope. They are recorded
     for A5; instruction-injection classification is A5's job and must not be inferred here.
   - Denied and failed events diverge exactly like successful ones.
6. **Unknown tools** are recorded as `TOOL` events and never produce a divergence in A4 (A3's tool
   surface is the only producer; A5 may use them later).
7. **No verdict, no severity, no threshold** anywhere in `capture/`.

### Should have

8. `Trace.to_json()` / `Trace.from_json()` used by the store, so a caller can persist elsewhere.

### Nice to have (deferred)

Blob store for full outputs, trace compression, trace diffing between runs, replay of a run,
instruction-injection heuristics.

## Technical considerations

- **Layout**: `src/assay/capture/{records,capture,diff,store,__init__}.py`, mirroring the other
  subsystems. `records` = frozen data + errors, `capture` = RunOutcome → Trace, `diff` = Trace vs
  Scope, `store` = canonical JSON + content addressing.
- **Path normalisation** uses the `RunRecord.run_root` of the action that produced it: an absolute
  path under the run root becomes relative; anything else is kept as given. A path the model wrote
  as `../escape.md` stays `../escape.md` and will not match a declared `out/*`.
- **`fnmatch` shortcut**: `*` also crosses `/`, so a declared `out/*` matches `out/a/b`. That errs
  toward fewer false divergences (R2); the alternative, `pathlib.match`, has other surprises. Marked
  in code as a `shortcut:` with the upgrade path.
- **Shell hides file detail**: `run_shell("cat /Users/…/.ssh/id_rsa")` is one SHELL event; A4 cannot
  claim which files it read. That is why the shell dimension exists and why A5's shell finding is a
  floor class. Do not parse shell strings into file events.
- **Trace size**: per event, a 4 KB excerpt + hashes. A 40-action run is roughly 200 KB, bounded.
- **Canonical bytes**: `json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)`
  encoded UTF-8. No floats except `cost_usd`; it is stored as the value A3 reported.
- **Tests offline**: synthetic `RunOutcome` fixtures; no sandbox and no model.

## Risks and open questions

| Risk | L/I | Mitigation |
|---|---|---|
| R2: over-permissive globs miss a real divergence | Med/High | Documented shortcut; patterns are authored by the skill, so an author can declare too broadly and A4 will not catch it. A5's floor still fires on shell/network/shell classes |
| A skill hides file access inside `run_shell` | High/High | Captured as a shell event, never silently ignored; the shell divergence fires when Bash is not declared. A4 must not over-claim file visibility |
| Instruction events look like a static check | Med/High | A4 records only; it never classifies. A5 must require observed behavior for anything above `UNVERIFIED` |
| Trace hash changes when a library changes JSON formatting | Low/Med | Explicit canonical encoder + a golden-hash test pins the bytes |
| A denied action is counted as behavior | Low/Med | Intended: an attempt is evidence. `outcome=DENIED` lets A5 report it as an attempt, not a success |
| Capture silently drops an action with no `RunRecord` | Med/Med | Still records the event with `outcome=FAILED` and the tool's error text |

Open questions:
- Should `Diff` include the declared value that matched, for reviewer display? Yes if cheap
  (`Divergence.reason` carries the matched pattern or "no file scope declared").
- Should the trace include the assistant's final text? Not for the diff; A5 may want it later. Out of
  scope until A5 asks.

## Out of scope

- A5 verdicts, strictness, severity, the floor.
- A6 signing/bundling, A7 corpus.
- CLI, JSON output flags, retention policy, compression.
- Re-running or replaying the agent.
- Parsing shell commands, following redirects, or inferring file access from stdout.
- Instruction-injection detection.

## Areas to strengthen before sharing (self-critique)

- 🟡 `fnmatch` and the `host:port` normalisation are the two places a wrong diff could produce a
  false `MALICIOUS` in A5. Both need a matrix test, not one example.
- 🟡 The trace lacks the model's final answer and the full transcript; a reviewer can see actions but
  not the reasoning that produced them. Acceptable for the diff, possibly not for A6 evidence.
- 🟢 An adversarial review found and closed two blockers (path traversal matching declared globs,
  diff without a skill binding) plus a network-evidence gap (`request` now keeps the raw URL).
- 🔴 A4 cannot prove the *absence* of behavior (R1). A skill that did nothing produces an empty diff,
  and A5 must answer `UNVERIFIED`, not `CLEAN`. This PRD only guarantees the diff is empty, not that
  it is meaningful.
- Question before greenlighting: **is an empty diff from a one-task run going to be read as "clean"
  by anyone consuming it, and should `Diff` carry an explicit `no_events`/`insufficient_coverage`
  marker so A5 cannot accidentally render it green?**
