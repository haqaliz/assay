# feat signed-bundle — signed attestation bundle (A6)

## Brief

Build A6 per `docs/technical/CAPABILITY_ROADMAP.md`: a signed, hash-listed
attestation bundle around an existing captured trace. `assay bundle <trace.json> --out DIR`
writes one canonical JSON record (schema/version, skill content hash, sandbox-policy
digest, trace file name + hash, the full assessment, signer key id) and signs it;
`assay verify <bundle>` re-derives the trace hash from the trace bytes, checks it equals
the assessment's `trace_hash` and that the skill hash matches, then verifies the
signature, exiting 0 verified / 1 tampered / 2 usage. Caveat: no Ed25519 exists in the
dependency set (`pyyaml` only, `cryptography` absent), so use `ssh-keygen -Y sign` /
`-Y verify` as the platform primitive with a throwaway key in tests and a named refusal
when the key is missing; the trace also carries no sandbox config today, so define a
policy digest rather than hashing the ephemeral run root. Acceptance: identical inputs
produce a byte-stable bundle; tampering with one trace byte, the verdict, or the
signature makes verify fail with a named reason and no traceback; an UNVERIFIED run
still bundles and verifies; `assay check`'s exit codes and JSON are unchanged. Docs must
state that a signature proves the record is intact and who attested it — never that the
skill is safe, and never more than "in this run" for CLEAN.

Source: A6 in `docs/technical/CAPABILITY_ROADMAP.md`; A5 shipped in `1724db3`, and this
is the next capability whose dependency is met. Selected by `assay-next` on 2026-11-01.

## Context carried from the pick

- Phase 0 gate met 2026-10-31 with a local model; A1–A5 and `assay check` shipped
  (549 offline tests, `c547` history). No GitHub issues exist; this card is the source.
- `docs/ROADMAP.md` M2.1: "Hash-listed, signed record of a run; a third party can verify it".
- `docs/technical/ARCHITECTURE.md`: bundle is `bundle/` (A6: hash list, signing, verify);
  CLI surface is `assay check | bundle | corpus`. Determinism: the replayable unit is the
  recorded trace, and the bundle carries the trace.
- Constraints: execution decides; no over-claim (a bundle attests a run, not safety);
  tests offline, no network, no real model call.
