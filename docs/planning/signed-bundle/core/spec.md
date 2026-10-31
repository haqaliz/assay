# Spec — `signed-bundle` / `core` (A6)

## Problem slice & user outcome

An assessed run becomes one canonical, signed file. A user can hand that file and their
public key to a third party, who runs one command offline and learns: which `SKILL.md`
hash was run, what the observed trace was, what verdict and findings A5 produced at which
strictness, which jail configs were used, and who signed the record. Nothing about the
skill is re-executed and no model is called.

## In scope

- `Trace` schema 2: `sandbox_config_hashes`, derived in `capture()` from
  `RunRecord.config_hash` of the actions that ran in a jail.
- `src/assay/bundle/`: `Bundle`, `HashList`, `Signature`; `build`, `verify`; SSH signing
  adapter (`ssh-keygen -Y`).
- `src/assay/canonical.py`: one canonical JSON helper shared by `cli/output.py` and
  `bundle/` (moved, byte-identical).
- `Finding.to_payload()` / `Assessment.to_payload()` in `verdict/records.py`; `render_json`
  reuses the finding mapping without changing its bytes.
- CLI: `assay bundle` and `assay verify`, with human/JSON output, named failure envelopes
  and exit codes.
- Docs/status sync: README, ARCHITECTURE, CAPABILITY_ROADMAP, ROADMAP, CLAUDE.md.
- Offline tests, including one real `ssh-keygen` round trip with a throwaway key.

## Out of scope

Verdict replay from a trace alone; carrying `Scope` or raw skill bytes in the trace;
key generation/management/revocation; multiple signatures, Sigstore, transparency logs;
registry/install-time verification; HTTP; attesting files other than `SKILL.md`; any change
to `assay check`, A5 semantics, or the four finding classes.

## Acceptance criteria

1. **Trace v2.** `Trace(schema=2, …, sandbox_config_hashes=(…))` validates each hash as
   `sha256:` + 64 lowercase hex, sorts and de-duplicates them, and emits them in
   `to_payload`. `Trace.from_json` accepts schema 2 and refuses schema 1 with a named
   `CaptureError`; `TraceStore.load` still enforces filename/content/canonical checks.
2. **Capture.** For a run whose actions entered jails with two distinct configs (for
   example `read_file` and `http_get`), `capture()` records exactly those two sorted hashes;
   a run with no recorded action records `()`. Actions with no `RunRecord` contribute
   nothing.
3. **Build.** `build(skill, trace, strictness, key)`:
   - raises `BundleError` when `skill.content_hash != trace.skill_content_hash`;
   - calls `assess` (no re-implementation) and stores its exact verdict, cause, blocked,
     strictness, findings and two hashes;
   - signs `canonical(unsigned payload)` and returns a `Bundle` whose `hash_list` is
     `skill = "sha256:" + assessment.skill_content_hash`, `trace = trace.hash`,
     `sandbox = trace.sandbox_config_hashes`.
4. **Bundle bytes.** `Bundle.to_json()` is one canonical line plus `\n`; the same trace,
   skill, strictness and key produce identical bytes on repeated builds; the signature
   covers the canonical payload with the `signature` key removed.
5. **Parse and validation.** `Bundle.from_json` requires the exact top-level key set,
   `schema: 1`, a one-line `SSHSIG` signature, a valid `Assessment` (all A5 invariants), a
   valid `Trace` (schema 2, canonical), and a `hash_list` that agrees with both. Any
   disagreement is a `BundleError` naming the mismatch.
6. **Verify success.** `verify(bundle, public_key)`:
   - reads at most 64 MiB of UTF-8;
   - requires `bundle.to_json() == file bytes` (rejects reformatting or unknown keys);
   - requires the supplied key's fingerprint to equal `signature.signer`;
   - verifies the signature over the rebuilt unsigned payload with `ssh-keygen -Y verify`
     in namespace `assay`;
   - returns `None` on success.
7. **Tamper matrix.** Each of these makes `verify` raise a `BundleError` (or
   `SigningError`) and the CLI exit `1` with a named cause, no traceback:
   a. one byte changed in the embedded trace (hash mismatch or signature failure);
   b. `verdict` flipped to `clean` (assessment/trace cross-check or signature failure);
   c. a finding added, removed or re-severitied;
   d. `hash_list.skill`/`trace`/`sandbox` edited;
   e. the signature value replaced;
   f. a bundle signed by key A verified with key B;
   g. extra top-level key, whitespace, or a second line added to the file;
   h. schema 1 bundle, malformed JSON, non-UTF-8, or a file over 64 MiB.
8. **CLI `bundle`.** `assay bundle <trace.json> --skill <SKILL.md|dir> --key <private-key>
   [--strictness …] [--out DIR] [--json]`:
   - writes `<trace-stem>.bundle.json` next to the trace by default, `--out` overrides and
     is created;
   - prints the verdict summary, the bundle path and the signer fingerprint; `--json` emits
     one canonical line with `schema`, `bundle`, `skill`, `verdict`, `strictness`, `blocked`,
     `findings`, `trace_hash`, `sandbox`, `signer`;
   - exit `0` on write; exit `1` with a named failure envelope for an unreadable/invalid
     trace, a skill hash mismatch, a missing/unreadable key or a signing failure; exit `2`
     for usage errors; exit `130` on Ctrl-C;
   - never prints the private key path or contents, and never writes the key path into the
     bundle.
9. **CLI `verify`.** `assay verify <bundle.json> --public-key <pub> [--json]`:
   - success prints verdict, skill hash, trace hash, sandbox hashes, signer and
     `signature: verified`; `--json` adds `"verified": true`;
   - every failure prints the bundle envelope (`schema`, `bundle`, `cause`, `detail`) and
     exits `1`; usage errors exit `2`;
   - no key contents or private material are printed.
10. **Docs.** README documents both commands, the dedicated-key recipe
    (`ssh-keygen -t ed25519 -N '' -f ~/.ssh/assay-attest`) and the limits; ARCHITECTURE
    documents the bundle format, the trust model and the corrected determinism sentence
    (the trace alone cannot re-derive the verdict); CAPABILITY_ROADMAP marks A6 built with the
    gap; ROADMAP records M2.1; CLAUDE.md's status paragraph stops saying there is no bundle.
11. **Suite.** `uv run pytest` is green and offline; the crypto test skips with a named
    reason when `ssh-keygen` is unavailable; `assay check`'s exact-byte and exit-code tests
    are unchanged.

## Dependencies & sequencing

Composes `parse_skill` (A1), `Trace`/`TraceStore`/`capture` (A4), `assess`/
`StrictnessPolicy` (A5), and the existing CLI conventions. No new Python dependency.

Order: trace v2 (records, capture, store tests) → bundle records/build/verify → signing
adapter → CLI → docs. Each step lands test-first; the CLI step is last so it composes
shipped functions.

## Open questions / risks

- **O1 replay gap** (see PRD): `verify` proves integrity and authenticity, not that the
  verdict follows from the trace. ARCHITECTURE must say this until the follow-on.
- `ssh-keygen` portability and passphrase prompts: named failures, bounded timeout, a
  skip-with-reason test; a `cryptography` backend can replace `sign.py` later.
- `JailConfig.config_hash` includes the run's staging directory, so sandbox hashes are
  per-run, not portable policy identifiers. Document; a readable policy record is a
  follow-on.
- A bundle can only be built while the original `SKILL.md` still hashes to the trace's
  value; this is deliberate, and the failure is named.
