# Spec — `bundle-replay` / `core` (A6 follow-on)

## Problem slice & user outcome

A bundle carries the exact `SKILL.md` that produced the trace, and `assay verify` re-runs the shipped
verdict layer over the embedded source + trace. A third party gets `signature: verified` and
`replay: verified` from one file and a public key; a signed but false assessment is refused. The trace
schema and the corpus are untouched.

## In scope

- `parse_skill_text` in `src/assay/ingest/` (text entry point, same parser, same hash).
- `SkillSource` and bundle schema 2 in `src/assay/bundle/records.py`.
- `create_bundle`/`build` source parameter; `replay`; `verify` = signature + replay.
- CLI `bundle` reads/passes the source; `verify` prints `replay: verified` / `"replay": true` and maps
  `replay-mismatch`.
- Docs/status: README, ARCHITECTURE, CAPABILITY_ROADMAP, ROADMAP, CLAUDE.md.
- Offline tests, including a re-signed false assessment and a corpus-case bundle.

## Out of scope

Trace schema 3; corpus regeneration; A5 changes; key management; multiple signatures; public audit;
adapters; hosted verification; proving the capture or the rest of the skill directory.

## Bundle payload (schema 2)

```json
{"schema":2,
 "hash_list":{"skill":"sha256:<64hex>","trace":"<64hex>","sandbox":["sha256:<64hex>"]},
 "skill":{"content_hash":"sha256:<64hex>","source":"<exact SKILL.md text>"},
 "trace":{...},
 "assessment":{...},
 "signature":{"namespace":"assay","signer":"SHA256:…","value":"…"}}
```

- Exact top-level keys `{schema, hash_list, skill, trace, assessment, signature}`.
- Exact `skill` keys `{content_hash, source}`; `source` non-empty and at most `MAX_SKILL_BYTES`.
- `skill.content_hash == hash_list.skill == "sha256:" + trace.skill_content_hash ==
  "sha256:" + assessment.skill_content_hash`; `sha256(source.encode("utf-8"))` equals the hash.
- `hash_list.trace == trace.hash == assessment.trace_hash`; `hash_list.sandbox ==
  trace.sandbox_config_hashes`.
- The signature covers `canonical(payload without "signature")`; the file is `canonical(payload)`.
- Schema 1 → `BundleError("bundle-invalid: bundle schema 1 is not replayable; rebuild it")`.

## Replay

```python
def replay(bundle: Bundle) -> Assessment
```

1. `parse_skill_text(bundle.skill.source, Path("SKILL.md"))`; `SkillParseError` →
   `bundle-invalid`/`replay-mismatch` with the cause.
2. Parsed `content_hash` must equal `bundle.trace.skill_content_hash` (the `Bundle` already checks the
   source hash; this is the parse-level check).
3. `assess(parsed, bundle.trace, policy=StrictnessPolicy(level=bundle.assessment.strictness))`.
4. The result must equal the stored `Assessment` exactly; otherwise
   `BundleError("replay-mismatch: …")`.
5. Return the derived assessment.

## Acceptance criteria

1. **Text ingest.** `parse_skill_text(text, path)` returns the same `Skill` fields and
   `content_hash` as `parse_skill(path)` for a UTF-8 file, including BOM/CRLF inputs; non-str,
   unencodable text, oversized text and malformed frontmatter raise `SkillParseError` with the
   existing causes. `parse_skill` behaviour is unchanged.
2. **Schema 2 records.** `SkillSource` validates a `sha256:` hash, a non-empty string source, the
   size cap and `sha256(source) == content_hash`. `Bundle.to_json()` has the schema-2 payload and is
   canonical; `Bundle.from_json(to_json()) == bundle`; a schema-1 payload is refused by name; an
   unknown top-level or `skill` key is `bundle-invalid`; a non-canonical file is `bundle-not-canonical`.
3. **Hash cross-checks.** A source whose hash differs from the trace/assessment, a hash list
   mismatch, or a source over `MAX_SKILL_BYTES` is a `BundleError` with `hash-mismatch`/`bundle-invalid`.
4. **Build.** `create_bundle(skill, source, trace, strictness, signer)` refuses `source` that does not
   hash to `skill.content_hash` (`skill-mismatch`); it signs the canonical unsigned payload including
   `skill`; `build(..., private_key)` binds the real signer. The CLI passes the exact file source
   (bytes decoded UTF-8, not newline-normalised).
5. **Replay success.** A bundle built from a real skill/trace verifies and replays; the derived
   assessment equals the stored one; `replay(bundle)` returns it.
6. **Replay failure.** A bundle with a valid signature but an assessment that does not follow from
   the skill + trace raises `replay-mismatch`. Construct it by replacing the assessment with a valid
   but different one (e.g. `CLEAN` with no findings where `assess` yields `FLAGGED`) and re-signing
   with the same key; `assay verify` exits `1` with `REPLAY_MISMATCH`.
7. **Signature still first.** A tampered trace/skill/hash list/signature fails with its existing
   cause (hash-mismatch, bundle-invalid, signature-invalid) before or during replay; no traceback.
8. **CLI output.** `assay verify` human output adds `replay: verified` after `signature: verified`;
   `--json` adds `"replay": true`. `assay bundle` output/exit codes and `assay check` are unchanged.
9. **No corpus change.** All 20 corpus traces stay schema 2 and load; `assay corpus` output is
   unchanged; bundling a corpus case builds and replays.
10. **Docs.** README, ARCHITECTURE (payload, replay, corrected determinism), CAPABILITY_ROADMAP A6,
    ROADMAP, CLAUDE.md updated. Limits stated: replay proves derivation, not capture; `SKILL.md`
    only; schema-1 bundles are refused.
11. **Suite.** `uv run pytest` green and offline; no new dependency.

## Dependencies & sequencing

Uses A1 (`parse_skill_text`), A4 (`Trace` schema 2), A5 (`assess`/`StrictnessPolicy`), A6 (`Bundle`,
`sign`/`verify`). No corpus or trace change. Order: ingest text → bundle schema/replay → CLI → docs.

## Open questions / risks

- Parser drift breaks old bundles; the bundle schema is the replay contract.
- Schema 1 bundles stop verifying (pre-0.1; rebuild).
- Replay is derivation, not capture proof; docs must say so.
- The embedded source is parsed, never executed; the 64 MiB verify cap remains.
