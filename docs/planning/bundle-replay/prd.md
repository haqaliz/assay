# PRD — `bundle-replay` (A6 follow-on: self-proving bundles)

Status: approved 2026-11-03 (user pre-approval through implementation). Date: 2026-11-03.
Pipeline position: follow-on to A6, before A8. No new capability ID; it closes the replay gap named
in the A6 PRD (O1) and `docs/technical/ARCHITECTURE.md`.

## Problem statement

A signed bundle proves that a record is intact and who attested it. It does not prove that the
verdict follows from the record. A signer can sign a false `CLEAN`; a third party has no way to
check the claim except by trusting the signer. The moat claim is **signed replay**, not signed
claims: a verifier should be able to re-run the verdict layer from the bundle alone and reject a
record that does not add up.

Two facts block that today:

- the trace carries only the skill hash, not the declared scope or the body/description that A5's
  instruction scan reads;
- `assay verify` checks the signature and the hash list only.

The fix belongs in the bundle, not the trace: the bundle already carries the trace and the
assessment, and `assay bundle` already has the exact `SKILL.md` at build time. Embedding the source
closes the gap without a trace schema change or a corpus regeneration.

For whom: a reviewer of a published finding, a registry/CI consumer, and the maintainer defending a
verdict without asking anyone to trust the signer.

## Goals and success metrics

| Goal | Metric |
|---|---|
| The bundle carries its inputs | Bundle schema 2 contains the exact `SKILL.md` source (capped by `MAX_SKILL_BYTES`) plus the trace and assessment |
| Verify re-derives the verdict | `assay verify` re-parses the source, re-runs the shipped `assess` at the recorded strictness, and prints `replay: verified` |
| A signed lie fails | A valid signature over an assessment that does not follow from the embedded skill and trace exits `1` with `replay-mismatch` |
| Integrity still fails first | A tampered trace, hash list, skill source or signature still fails with its existing named cause |
| No collateral change | `assay check`, the trace schema (2), the corpus, A5 and the bundle's hash checks are unchanged; the suite stays green and offline |
| Honest limits | Docs say the replay proves derivation from the recorded `SKILL.md` + trace, not that the run happened or that the skill directory is unchanged |

## Users and scenarios

1. **Reviewer of a `MALICIOUS` finding** — runs `assay verify` with the author's public key and sees
   both `signature: verified` and `replay: verified`, then reads the finding.
2. **Registry/CI** — rejects a bundle whose signed verdict does not follow from its own inputs.
3. **Maintainer** — publishes a bundle without asking anyone to trust the verdict as an assertion.

## Requirements

### Must have

1. **Text ingest.** `parse_skill_text(text: str, path: Path = Path("SKILL.md")) -> Skill` parses the
   same way as `parse_skill` and computes `content_hash` over `text.encode("utf-8")`; it enforces
   `MAX_SKILL_BYTES`, rejects non-strings and unencodable text with a named `SkillParseError`, and
   returns identical fields/hashes to `parse_skill` for the same bytes.
2. **Bundle schema 2.** The canonical payload is:
   ```json
   {"schema":2,
    "hash_list":{"skill":"sha256:<hex>","trace":"<hex>","sandbox":["sha256:<hex>"]},
    "skill":{"content_hash":"sha256:<hex>","source":"<exact SKILL.md text>"},
    "trace":{...},
    "assessment":{...},
    "signature":{...}}
   ```
   - `skill.content_hash` equals `hash_list.skill`, and `sha256(skill.source)` equals both and
     `trace.skill_content_hash`/`assessment.skill_content_hash`.
   - `source` is non-empty, at most `MAX_SKILL_BYTES`, and is never executed.
   - The signature covers the canonical payload without `signature`, including the skill source.
   - Schema 1 is refused with `bundle-invalid: bundle schema 1 is not replayable; rebuild it`.
3. **Build.** `create_bundle(skill, skill_source, trace, strictness, signer)` and
   `build(skill, skill_source, trace, strictness, private_key)` take the raw source; they refuse a
   source whose hash does not equal `skill.content_hash` with `skill-mismatch`. The CLI reads the
   source from the `--skill` file (bytes decoded as UTF-8, not newline-normalised) and passes it.
4. **Replay.** `replay(bundle) -> Assessment`:
   - parses `bundle.skill.source` with `parse_skill_text`;
   - requires the parsed hash to equal `bundle.trace.skill_content_hash`;
   - calls the shipped `assess(parsed, bundle.trace, StrictnessPolicy(level=bundle.assessment.strictness))`;
   - requires the result to equal the stored `Assessment` exactly (verdict, findings, cause,
     blocked, strictness, both hashes);
   - raises `BundleError("replay-mismatch: …")` on any difference, parse failure or assessment
     error. No A5 logic is duplicated.
5. **Verify.** `verify(bundle, public_key)` checks the signature first, then replays. The CLI
   `assay verify` prints `replay: verified` (JSON `"replay": true`) after `signature: verified`; a
   `BundleError` from replay uses the existing bundle failure envelope with cause `REPLAY_MISMATCH`.
6. **No collateral change.** Trace schema stays 2; the corpus is not regenerated; `assay check`,
   `assay bundle`'s output path/exit codes, A5, the four classes and the verdict contract are
   unchanged. `assay bundle` embeds the source and grows the file; the 64 MiB verify cap stays.
7. **Docs.** README (bundle section, schema 2, replay), ARCHITECTURE (payload, replay algorithm,
   corrected determinism claim: the bundle replays, a bare trace does not), CAPABILITY_ROADMAP A6
   (replay built), ROADMAP progress, CLAUDE.md status. Every doc keeps the limits: `SKILL.md` only,
   not the skill directory; replay proves derivation, not that the run happened; the signer still
   attests the capture.
8. **Tests are offline.** Real `ssh-keygen` only through the existing throwaway-key pattern; no
   model, network or sandbox.

### Should have

9. A CLI test that re-signs a false assessment with the test key and gets `REPLAY_MISMATCH`, proving
   the replay is not just the signature.
10. A test that a bundle of a corpus case (schema-2 trace) builds and replays, showing the corpus
    needs no regeneration.
11. `replay` returns the derived `Assessment` for callers that want it, not just `None`.

### Nice to have (deferred)

Trace schema 3 carrying the scope/body so a bare trace replays; a `--trace-only` verify; signed
corpus reports; a parser-version pin in the bundle; multiple signatures.

## Technical considerations

- **Why the bundle, not the trace.** Adding the skill source to `Trace` would bump the trace schema
  and invalidate all 20 corpus traces (and every saved trace); the bundle is the publication unit and
  already has the skill at build time. Trace schema 2 stays.
- **Why `parse_skill_text`.** `assess` needs a `Skill`, not raw text. Re-parsing the embedded source
  with the same parser is the only way to reconstruct name, description, scope, body and hash
  without duplicating the parser. The source hash pins the bytes; the parser is deterministic.
- **Parser drift.** A future parser change could make an old bundle fail replay even though its
  signature is valid. The bundle schema is the replay contract: bump it when the replay semantics
  change, and keep old verification code or document the break. Pre-0.1, schema 2 is the only
  accepted version.
- **Security.** The embedded source is untrusted data: it is hashed and parsed, never written to
  disk, imported or executed. YAML parsing carries the existing frontmatter limits. The replay is
  pure `assess`; no model, network or sandbox.
- **Size.** `SKILL.md` is capped at `MAX_SKILL_BYTES` by ingest; the bundle grows by that amount. The
  CLI verify cap stays 64 MiB.
- **Not a capture proof.** Replay proves the verdict follows from the recorded trace + source. It
  does not prove the trace was captured honestly; the signature attests the capture. Say so.

## Risks and open questions

| Risk | L/I | Mitigation |
|---|---|---|
| Parser drift breaks old bundles | Med/Med | Bundle schema is the replay contract; bump it on semantic change; document |
| A signer embeds a different skill than the one that ran | High/Med | The source hash must equal the trace's `skill_content_hash`; the trace hash is signed |
| A signed false verdict still passes | High/High | The replay re-runs `assess` and compares exactly; a dedicated signed-lie test |
| Bundle size grows | Low/Low | `MAX_SKILL_BYTES` cap; 64 MiB verify cap |
| Schema 1 bundles stop verifying | Low/Med | Pre-0.1, named refusal, one-day-old artifacts; rebuild |
| Replay is read as "the run happened" | Med/High | Docs: replay proves derivation; the signature attests the capture; `SKILL.md` only |
| Embedded source is malicious | Low/Med | Parsed and hashed only; never executed; no new parser surface |

Open questions (recommendations):

- **O1 — pin the parser version?** [Not now; the bundle schema is the contract. Add a version field
  if parser changes become frequent.]
- **O2 — keep schema 1 support?** [No; it cannot replay. Refuse with a named cause and rebuild.]
- **O3 — replay on `assay bundle`?** [Build already calls `assess`; replay is for `verify`. A build-time
  self-check is implicit in `create_bundle`.]
- **O4 — trace schema 3?** [Later; the bundle is self-contained. A bare trace replay is a separate
  slice only if traces are published without bundles.]

Challenge: **if the signer can choose what to embed, what does replay add?** It removes the gap
between "signed claim" and "signed inputs": the verifier checks that the verdict follows from the
exact bytes the signer committed to. A signer who embeds a different skill than the one that ran is
caught by the signed trace hash; a signer who signs a false verdict is caught by replay. What
remains is whether the capture itself is honest, which no offline artifact can prove; the signature
and the sandbox are the answer there.

## Out of scope

- Trace schema 3 or any trace/corpus regeneration.
- A5 changes, tuning, new patterns or severity changes.
- Key management, rotation, revocation, multiple signatures, Sigstore.
- Proving the run happened, the skill directory beyond `SKILL.md`, or the model's behavior.
- Public audit/disclosure (M2.3/R3), adapters (A8), hosted verification (A9).

## Areas to strengthen before sharing (self-critique)

- 🔴 **Replay is not capture proof.** The bundle can be internally consistent and still be built from
  a fabricated trace. The signature says who built it; replay says it is self-consistent. Docs must
  not upgrade this to "the skill did X".
- 🟡 **Parser coupling.** The bundle's replay depends on the current parser semantics; a schema bump
  is a breaking change for old bundles.
- 🟡 **`SKILL.md` only.** The source covers the exact file, not scripts or data files it references.
- 🟡 **Schema 1 break.** One-day-old bundles stop verifying; acceptable pre-0.1, but state it.
- Question before greenlighting: **should `verify` fail when replay is unavailable (old schema) or
  warn?** [Fail: a signed verdict that cannot be re-derived is not the artifact we are selling.]
