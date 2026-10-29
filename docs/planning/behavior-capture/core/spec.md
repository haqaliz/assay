# Spec — `behavior-capture` / `core` (A4)

## Problem slice & user outcome

Turn one A3 run into a canonical, content-addressed trace of what the skill did, and diff that trace
against the skill's declared scope. A5 can later re-derive a verdict from the trace alone: no re-run,
no model call, no sandbox.

## In scope

- `EventKind`, `EventOutcome`, `Event`, `Trace`, `CaptureError`, `TraceIntegrityError`.
- `capture(skill, task, outcome) -> Trace`.
- `Divergence`, `Diff`, `Coverage`, `Dimension`, `DimensionStatus`; `diff(skill, trace) -> Diff`.
- `TraceStore(root).save/load` over canonical JSON.
- Offline unit tests; golden-hash test pins the encoding.

## Out of scope

A5 verdicts/severity/thresholds, A6 signing, A7 corpus, CLI, blob store, compression, replay,
shell parsing, instruction classification, cross-run trace diffing.

## Acceptance criteria

1. `capture` maps tool names: `read_file→FILE_READ`, `write_file→FILE_WRITE`, `http_get→NETWORK`,
   `run_shell→SHELL`, anything else→TOOL; exactly one event per action, in order.
2. Two INSTRUCTION events are always appended: `target="system"` hashes `skill.body`,
   `target="user"` hashes `task`.
3. `Event.outcome`: `OK` when the action's `RunRecord.ok`; `DENIED` when not ok and the record has
   denials; `FAILED` otherwise (including no record). The trace content is
   `RunRecord.stdout + stderr` when a record exists, else the tool's output; `truncated` mirrors the
   record.
4. `write_file` sets `input_sha256` to sha256 of the model-supplied content; every other kind has
   `None`.
5. `content_sha256`/`content_bytes` are over the UTF-8 of the event content (tool output, or
   instruction text); `excerpt` is at most 4096 bytes, valid UTF-8.
6. File targets are normalised with `posixpath.normpath` and made relative to the action's
   `RunRecord.run_root`; when that root still exists the path is resolved, so a symlink that leaves
   the root is recorded as its real absolute target. Escaping paths (`../`, traversal) never match a
   relative declaration.
7. Network targets are canonical `host:port` (lowercase, trailing dot stripped, IPs compressed,
   explicit port respected, default 443 for https and 80 for http). The raw URL is kept in
   `Event.request`. A URL that cannot be parsed is kept verbatim as the target.
8. `Trace` carries `schema=1`, `skill_name`, `skill_content_hash`, `task_sha256`, `cause`,
   `input_tokens`, `output_tokens`, `cost_usd`, `events`. `Trace.hash` = sha256 of canonical JSON;
   identical inputs give the same hash twice; a changed event changes it.
9. `TraceStore.save` writes `<hash>.json` atomically and returns the path; `load` verifies the hash
   and raises `TraceIntegrityError` when the file was edited or renamed.
10. `diff` file matrix: `files is None` → every file event is `UNDECLARED`; `files == ()` →
    `EXCEEDED`; matching pattern → no divergence; non-matching → `EXCEEDED`.
11. `diff` network matrix: `None` → `UNDECLARED`; `()` → `EXCEEDED`; exact `host:port` match (case
    insensitive, missing declared port = 443) → none; otherwise `EXCEEDED`.
12. `diff` shell matrix: `tools is None` → `UNDECLARED`; tools containing `Bash` or `Bash(...)` → no
    divergence; otherwise `EXCEEDED`.
13. Instructions and TOOL events never produce divergences. Coverage counts instructions with
    `declared=False` (there is no instruction key in `Scope`); TOOL has no coverage row.
14. Denied and failed events diverge exactly like successful ones, with their outcome preserved.
15. `diff` refuses a trace whose `skill_content_hash` differs from the skill's `content_hash`, and
    `Diff` carries both hashes.
16. A denied or failed divergence carries the event's outcome and denials.
17. No verdict, severity or threshold appears in `src/assay/capture/`; no network/model/sandbox in
    the suite.

## Dependencies & sequencing

Consumes `assay.ingest.Skill`/`Scope`, `assay.agent.RunOutcome`/`ToolAction`/`Usage`, and
`assay.sandbox.RunRecord`. No new dependency.

## Open questions / risks

- `fnmatch` lets `*` cross `/`; marked shortcut. Over-permissive, not over-flagging.
- Shell events hide which files were read; never parse shell strings.
- Trace has no final text; A5 may ask later.
