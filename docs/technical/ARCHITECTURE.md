# Assay: Architecture

Design intent, not a description of built behavior. **A1 (`src/assay/ingest/`), A2
(`src/assay/sandbox/`), A3 (`src/assay/agent/`), A4 (`src/assay/capture/`), A5
(`src/assay/verdict/`) and A6 (`src/assay/bundle/`) are implemented**; everything else below is
still intent — verify against the code and `git log`. A4 records and diffs observed behavior; A5
turns that diff into one assessment; A6 signs the trace, the assessment and the sandbox config
hashes into a portable record. The manual Anthropic-keyed gate run is still unperformed; the Phase 0
gate ran a local model.

## Pipeline

```
skill (SKILL.md | ClawHub | Cursor rule | MCP manifest)
        |
        v
  A1 ingest  ---->  Skill record (declared scope)
        |
        v
  A2 sandbox  <----  jail config (fs, network, env, limits)
        |
        v
  A3 agent driver (BYOK)  --  one task from the skill's stated purpose
        |
        v
  A4 capture  ---->  content-addressed event trace (file, net, shell, instruction)
        |
        v
  A4 diff     ---->  observed vs declared
        |
        v
  A5 verdict  ---->  CLEAN | FLAGGED | MALICIOUS | UNVERIFIED  (+ named cause)
        |
        +-->  A7 findings corpus
        v
  A6 signed bundle
```

## Layout

```
src/assay/
  ingest/     A1: parsers per format, Skill record   ← built (Claude Code SKILL.md)
  sandbox/    A2: jail setup, limits, teardown   ← built (macOS Seatbelt)
  agent/      A3: driver, task generation, cost caps   ← built (Anthropic + OpenAI-compatible)
  capture/    A4: event recorder, trace store, diff   ← built (canonical traces, scope diff)
  verdict/    A5: findings, strictness, floor   ← built (assessment, pattern lists)
  bundle/     A6: hash list, signing, verify   ← built (SSH-signed canonical record)
  corpus/     A7: labeled cases, metrics
  cli/        assay check | bundle | verify
tests/        offline; recorded traces; no network, no model calls
```

## Key decisions

- **Sandbox first.** Every skill runs only inside the jail. The jail is the first thing built and
  the most heavily tested; escape attempts are test cases.
- **Observation over inference.** Verdicts above `UNVERIFIED` need a captured event. Static
  signals only order the work.
- **Strictness model.** Levels (for example `baseline`, `standard`, `strict`) change which
  findings block, never the verdict they produce. A hard floor defines minimum severities for the
  four classes; any policy that tries to change it is rejected at construction. An instruction
  match is capped at `REVIEW`, so it can never become `MALICIOUS`.
- **Determinism.** The agent is non-deterministic, so the recorded unit is the *trace*, not a
  re-run. The bundle carries the trace and embeds the assessment A5 produced at build time.
  `assay verify` checks the record's hashes and signature; it does **not** re-derive the verdict,
  because the trace does not yet carry the declared scope or the full skill body. That replay is
  the first follow-on (see Open questions). The bundle therefore attests what was run and what
  verdict was reached, not that the verdict follows from the trace alone.
- **Tests run offline.** The agent driver sits behind an injectable seam; CI uses recorded traces.
  No model call and no network in any test.
- **BYOK.** Keys live in the environment of the user, are never committed, and are never defaults.
- **UNVERIFIED causes.** A5 names `NO_TRIGGER`, `NO_DECLARED_SCOPE`, `AGENT_FAILED`,
  `BUDGET_LIMIT` (step/action/wall stop) and `COST_CAPPED`. A skill that will not parse is refused before a trace exists; the CLI maps that
  to `UNVERIFIED/WONT_PARSE`, and a missing sandbox to `UNVERIFIED/SANDBOX_UNAVAILABLE`.

## CLI

`assay check <skill>` composes A1–A5: parse, model (`AnthropicModel.from_env`), sandbox
(`select_sandbox`), a private run root, `task_for`, `drive`, `capture`, `TraceStore(out).save`,
`assess`, then a human or JSON report. It adds no detection logic.

```
assay check <skill> [--strictness baseline|standard|strict]
                    --max-cost USD --model NAME --input-price USD_PER_MTOK
                    --output-price USD_PER_MTOK
                    [--max-steps 20] [--max-actions 40] [--max-wall-seconds 300]
                    [--out ./.assay/traces] [--json] [--keep-run-root]
```

The four cost/model settings are required (model and prices also fall back to `ASSAY_MODEL`,
`ASSAY_INPUT_PRICE`, `ASSAY_OUTPUT_PRICE`; the cap to `ASSAY_MAX_COST`). The default trace
directory resolves against the invocation directory. `--json` is one canonical line
(`sort_keys`, compact separators, UTF-8, trailing newline) with a versioned `schema`; identical
runs produce identical bytes.

Exit is verdict-only: `0` on `CLEAN`, `1` on `FLAGGED/MALICIOUS/UNVERIFIED`, `2` on a usage or
config error, `130` on Ctrl-C. `blocked` is reported but never changes the code.
Parse and sandbox refusals use a `UNVERIFIED` envelope and exit `1`; no other failure prints a
traceback. The API key is read from `ANTHROPIC_API_KEY` and never reaches stdout, the JSON, the
trace or `JailConfig.env`. The first real keyed run is still the maintainer's; the suite injects a
scripted model and fake sandbox.

```
assay bundle <trace.json> --skill <SKILL.md|dir> --key <private-key>
             [--strictness baseline|standard|strict] [--out DIR] [--json]
assay verify <bundle.json> --public-key <pub> [--json]
```

`bundle` re-parses the skill (refusing unless its hash equals the trace's), re-runs `assess` at the
chosen strictness, and signs the canonical record with `ssh-keygen -Y sign -n assay`. It defaults
to writing `<trace-stem>.bundle.json` next to the trace. `verify` reads at most 64 MiB, requires the
file to be the canonical encoding, checks every hash against the embedded trace and assessment, and
verifies the signature against the public key the caller supplies. Both exit `0` on success, `1` on
a named failure, `2` on a usage error, `130` on Ctrl-C; failures use a `bundle` envelope with
`schema`, `bundle`, `cause` and `detail`.

## Bundle (A6)

One canonical JSON line:

```json
{"schema":1,
 "hash_list":{"skill":"sha256:<hex>","trace":"<hex>","sandbox":["sha256:<hex>"]},
 "trace":{...},
 "assessment":{"verdict":"…","cause":…,"blocked":…,"strictness":"…","findings":[…],
               "skill_content_hash":"<hex>","trace_hash":"<hex>"},
 "signature":{"namespace":"assay","signer":"SHA256:<fingerprint>","value":"-----BEGIN SSH SIGNATURE-----…"}}
```

- The signature covers `canonical(payload without "signature")`; the file itself is the canonical
  encoding of the whole payload. Any reformatting or extra key is refused before the signature is
  checked.
- The trace is embedded, so a verifier needs only the bundle and the signer's public key.
- `verify` requires an explicit `--public-key`. A bundle never supplies its own trust anchor; the
  signer fingerprint is informational and is checked against the supplied key.
- `Trace` schema 2 records `sandbox_config_hashes`: the sorted, de-duplicated
  `JailConfig.config_hash` values of the actions that entered a jail. They identify this run's
  configs (including its private staging path) and are not a portable policy version.
- What is attested: the `SKILL.md` hash, the captured trace, the sandbox config hashes, and the A5
  assessment at the recorded strictness. Not attested: that the skill is safe, that the rest of the
  skill directory is unchanged, or that the verdict follows from the trace alone. `CLEAN` still
  means "matched declared scope in this run".

## Open questions

- ~~Sandbox technology on macOS and Linux (Seatbelt, containers, or both)~~ **Decided:** Seatbelt
  only, behind a `Sandbox` seam (A2). Docker was rejected as a daemon dependency with no A2
  benefit; the probe evidence and the Linux consequence are in
  `docs/planning/sandbox-jail/prd.md`. A Linux backend is a follow-on slice.
- **Verdict replay.** `verify` cannot re-derive the verdict from the bundle: the trace carries
  neither the declared `Scope` nor the full skill body that A5's instruction scan uses. The next
  slice either carries both in the trace (schema 3) and re-runs `assess` at verify time, or accepts
  that a bundle attests a reported verdict only. A readable sandbox policy record is a smaller
  follow-on.
- How to generate synthetic tasks that exercise a skill without an LLM judging the outcome.
- Distribution name on PyPI: `assay` is taken; `assayhq` was free when checked.
