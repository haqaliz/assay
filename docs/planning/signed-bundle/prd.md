# PRD — `signed-bundle` (A6: signed attestation bundle)

Status: draft for review. Date: 2026-11-01.
Pipeline position: Phase 2, milestone M2.1. A6 sits after A5 and before A7: it turns an
assessed run into a portable record a third party can check, and is the unit A7's corpus
will label. No new detection logic.

## Problem statement

Assay can now produce a verdict (`assay check`, A1–A5), but the verdict and its evidence
live only on the machine that ran it. A `MALICIOUS` finding cannot be handed to a skill
author or a registry with any proof that the trace behind it was not edited afterwards, and
a `CLEAN` run cannot be cited as evidence because there is nothing binding the report to
the run. The dogfood output (`~/Desktop/assay-dogfood-2026-10-31/`) is a directory of
unsigned traces; nothing in it is third-party verifiable.

A6 makes the run portable: one signed file that carries the skill hash, the observed trace,
the verdict, and the sandbox configuration the run was confined by, which anyone can verify
offline with the signer's public key.

For whom: the maintainer publishing an audit, a skill author attaching evidence to a
release, and a registry/CI gate that must check a claim without spending tokens or running
an untrusted skill.

## Goals and success metrics

| Goal | Metric |
|---|---|
| A run becomes one portable file | `assay bundle <trace> --skill <SKILL.md> --key <key>` writes `<trace-hash>.bundle.json` (or `--out DIR/<trace-hash>.bundle.json`) |
| Integrity is checkable offline | `assay verify <bundle> --public-key <pub>` exits `0` and prints `signature: verified` |
| Tampering is caught | Any single-byte change to the embedded trace, a flipped verdict/finding, an edited hash list, a replaced signature, or the wrong public key exits `1` with a named cause and no traceback |
| Deterministic artifact | The same trace, skill and key produce byte-identical bundle bytes (Ed25519/SSH signatures are deterministic) |
| Honest scope | The bundle attests a run and a `SKILL.md` hash, never that the skill is safe, and never claims a `CLEAN` beyond "in this run" |
| Nothing else changes | `assay check` output bytes and exit codes are unchanged; the suite stays green and offline |

## Users and scenarios

1. **Maintainer attesting an audit** — runs `assay check`, keeps the trace, then bundles it
   with a dedicated SSH key and publishes the bundle plus the public key.
2. **Skill author** — bundles a `CLEAN` run and attaches it to a release; readers verify it
   and see the strictness and the exact skill hash it applies to.
3. **Registry or CI** — receives a bundle, verifies it with the author's published key, and
   reads the verdict and findings without running the skill or spending tokens.
4. **Reviewer of a `MALICIOUS` finding** — opens the bundle, reads the embedded trace and
   findings, and checks the signature before contacting the author (R2/R3 discipline).

## Requirements

### Must have

1. **Trace schema 2 carries the sandbox identity.** `Trace` gains
   `sandbox_config_hashes: tuple[str, ...]`: the sorted, de-duplicated
   `RunRecord.config_hash` values of every action that actually entered a jail, derived in
   `capture()` from `outcome.actions`. Empty when no action ran. `schema` becomes `2`;
   a stored schema-1 trace is refused by name (`Trace` must not silently reinterpret it).
2. **Bundle builder.** `assay bundle <trace.json> --skill <SKILL.md> --key <private-key>
   [--strictness baseline|standard|strict] [--out DIR] [--json]`:
   - loads the trace through `TraceStore.load` (content address + canonical form),
   - parses the skill and refuses unless its `content_hash` equals `trace.skill_content_hash`,
   - re-assesses with `assess(skill, trace, StrictnessPolicy(level))`, so the signed verdict
     is exactly the verdict the shipped A5 code produces for that trace,
   - signs the canonical unsigned payload with `ssh-keygen -Y sign -n assay`,
   - writes one canonical JSON line atomically; default path is next to the trace as
     `<trace-stem>.bundle.json`.
3. **Bundle payload** (canonical JSON, `schema: 1`):
   ```json
   {
     "schema": 1,
     "hash_list": {
       "skill": "sha256:<64 hex>",
       "trace": "<64 hex>",
       "sandbox": ["sha256:<64 hex>", "..."]
     },
     "trace": { "…": "Trace.to_payload()" },
     "assessment": {
       "verdict": "clean|flagged|malicious|unverified",
       "cause": null,
       "blocked": false,
       "strictness": "standard",
       "findings": [],
       "skill_content_hash": "<64 hex>",
       "trace_hash": "<64 hex>"
     },
     "signature": {
       "namespace": "assay",
       "signer": "SHA256:<fingerprint>",
       "value": "-----BEGIN SSH SIGNATURE-----\n…"
     }
   }
   ```
   The signature covers `canonical(payload without "signature")`; the file is
   `canonical(payload)`, one line plus `\n`.
4. **Verifier.** `assay verify <bundle.json> --public-key <pub> [--json]`:
   - reads at most 64 MiB and requires UTF-8,
   - parses the bundle, then requires `bundle.to_json() == file bytes` (canonical form; no
     extra keys, no reformatting),
   - checks `signature.signer` equals the fingerprint of `--public-key`,
   - verifies the signature over the rebuilt unsigned payload,
   - cross-checks `hash_list` against the embedded trace and assessment
     (`skill`, `trace`, `sandbox` all agree),
   - prints the verdict, the hashes, the signer and `signature: verified`.
   The public key is always supplied by the verifier; a bundle never supplies its own trust
   anchor.
5. **Named failures, no traceback.** Bundle/verify failures use a dedicated envelope
   (`schema`, `bundle` path, `cause`, `detail`), exit `1`. Causes at minimum:
   `trace-unreadable`, `trace-invalid`, `skill-mismatch`, `signing-key-unavailable`,
   `signing-failed`, `bundle-invalid`, `bundle-not-canonical`, `signer-mismatch`,
   `signature-invalid`, `hash-mismatch`. Usage/argument errors exit `2`; Ctrl-C exits `130`.
6. **Key hygiene.** The private key path is never written into the bundle, stdout, or JSON;
   only the public fingerprint is. The key is read by `ssh-keygen`, not by Assay. A
   passphrase-protected key that blocks is killed after a bounded timeout and reported as
   `signing-failed`, never a hang.
7. **Reuse the house conventions.** Canonical JSON (`sort_keys`, compact separators,
   `ensure_ascii=False`, trailing newline), verdict/finding vocabulary from A5, atomic
   write, and `assess` — no second verdict implementation.
8. **Docs and status.** README usage and status, ARCHITECTURE (bundle format, trust model,
   corrected determinism claim), CAPABILITY_ROADMAP (A6 built), ROADMAP progress/M2.1,
   CLAUDE.md status. Every doc states: a signature proves the record is intact and who
   attested it; it does not prove the skill is safe; `CLEAN` means "matched declared scope
   in this run"; the skill hash covers `SKILL.md` only, not the skill directory.
9. **Tests are offline.** A scripted model/fake sandbox for the end-to-end trace; a
   throwaway Ed25519 key generated under `tmp_path` for the real `ssh-keygen` path, skipped
   with a named reason when `ssh-keygen` is absent. No network, no model call, no real
   sandbox escape.

### Should have

10. `--json` for both commands; bundle human output reuses the check summary lines.
11. `--out DIR` creates the directory and reports the absolute bundle path.
12. `assay bundle` refuses a trace file whose name does not match its content hash (already
    enforced by `TraceStore.load`).

### Nice to have (deferred)

`assay bundle` from a trace without `--skill` (needs verdict replay, see below); `--keygen`;
multiple signatures; Sigstore/cosign; `assay install`; publishing a bundle over HTTP.

## Technical considerations

- **Why `bundle` takes `--skill`.** The trace carries no assessment and no declared scope,
  so a trace alone cannot produce a verdict. `bundle` therefore re-parses the skill, requires
  its hash to equal the trace's, and calls the shipped `assess`. This is also the guard that
  prevents bundling a different `SKILL.md` than the one that ran. `--strictness` defaults to
  `standard` (the `check` default); pass the same level the check used, and the bundle records
  it.
- **Why not `check --bundle`.** It would add a new flag and a new failure path to the one
  command whose output stability is a tested contract. The offline command keeps `check`
  untouched and lets an existing trace be attested later.
- **Sandbox identity.** `JailConfig.config_hash` already exists and deliberately excludes
  `run_root`/`keep`. It does include `allow_read_extra`, which contains the run's private
  staging directory, so the hashes identify this run's configs and are not comparable across
  runs. That is what the bundle needs; it is not a portable "policy version".
- **Module layout.** `src/assay/bundle/` (`records.py` for `Bundle`, `HashList`, `Signature`;
  `sign.py` for the `ssh-keygen` adapter; `build.py` for `build`/`verify`), `src/assay/canonical.py`
  shared by `cli/output.py` and `bundle/` (moved from `cli/output.py`, same bytes),
  `Finding.to_payload()`/`Assessment.to_payload()` in `verdict/records.py` so the bundle and
  the CLI share one finding mapping.
- **Signing primitive.** `ssh-keygen -Y sign -n assay -` over stdin, verified with
  `ssh-keygen -Y verify -f <allowed_signers> -I assay -n assay -s <sig> -`. Verified on the
  dev host: deterministic output, `255` on tamper, fingerprint available from
  `ssh-keygen -lf -`. No new Python dependency; `subprocess.run` with a bounded timeout,
  list argv, no shell.
- **Trust model.** `verify` requires `--public-key`. If the bundle carried (and trusted) its
  own key, an attacker could re-sign a forged record. The bundle's `signer` fingerprint is
  informational and is checked against the supplied key so a wrong key fails early.
- **Trace schema 2.** Existing schema-1 trace files stop loading (`Trace.from_json` refuses
  them by name). This is pre-0.1 run state; the dogfood traces are re-runnable. No migration.
- **Security.** Bundle/verify parse an input the verifier did not produce: size cap, canonical
  requirement, strict schema, no `eval`, no key contents in output. The private key is passed
  to `ssh-keygen` by path; the process environment is not logged.
- **Layering.** The bundle composes A1 (`parse_skill`), A4 (`Trace`/`TraceStore`), and A5
  (`assess`). It adds no detection logic and no new verdict vocabulary.

## Risks and open questions

| Risk | L/I | Mitigation |
|---|---|---|
| `ssh-keygen` is a platform dependency; Linux CI images usually have OpenSSH, Windows may not | Med/Med | Named `ssh-keygen-not-found` failure; the crypto test skips with a reason; the seam is one module, so a `cryptography` backend can replace it later |
| A passphrase-protected key prompts on a TTY and hangs the command | Med/Med | Bounded timeout; `signing-failed` with a one-line hint; docs recommend a dedicated passphrase-less attestation key |
| A signed bundle is read as "the skill is safe" | High/High | Docs and output say `signature: verified` and `verdict` separately; explicit honesty sentence in README/ARCHITECTURE; no `safe` field anywhere |
| The signer's key is compromised or the verifier trusts the wrong key | Med/High | Verify always takes an explicit `--public-key`; the fingerprint is printed; no embedded trust anchor |
| `--strictness` at bundle time differs from the check run | Med/Med | The bundle records and prints strictness; docs say to reuse the check level; default matches `check` |
| Trace schema 2 breaks old traces | Low/Med | Named refusal; pre-0.1 run state; no silent reinterpretation |
| A bundle is large (excerpts up to 4 KiB per event) | Low/Low | 64 MiB verify cap; typical runs are hundreds of KiB |

Open questions (recommendations in brackets):

- **O1 — Verdict replay.** `verify` checks integrity and authenticity, but cannot re-derive
  the verdict: the trace carries neither the declared scope nor the full skill body. Should
  A6 close that now (trace schema 2 also carries `Scope` and the raw `SKILL.md` bytes, and
  `verify` re-runs `assess`), or leave it as the next slice? [Leave it; ship signed evidence
  now, name the gap in ARCHITECTURE, and make replay the first follow-on. Otherwise A6
  becomes an A4 schema rewrite and the PR grows past its review value.]
- **O2 — Signing key selection.** `--key` required, no default key discovery. Should it fall
  back to `$ASSAY_SIGNING_KEY` or `~/.ssh/id_ed25519`? [No: implicit use of a personal key is
  a trust surprise; require the flag.]
- **O3 — Bundle filename.** `<trace-stem>.bundle.json` next to the trace by default. Should
  it be content-addressed like traces? [No: the trace hash already names it, and a stable
  name makes the publish step predictable.]
- **O4 — Trust anchor.** Require `--public-key` (chosen) versus embed and print the key
  (convenient, but a self-signed record proves little). [Require it.]

Challenge (the hard question before greenlighting): **if a third party still has to trust the
signer's key and cannot re-derive the verdict, what does the bundle prove that a checksum of
the JSON report does not?** The answer this slice relies on: it binds the verdict to the
observed trace, the exact `SKILL.md` hash and the sandbox configs, under one signature, so
neither the record nor the claim can be edited after the fact — and it is the artifact A7
will label and a registry will check. That answer is weaker until O1 is closed; say so in the
docs.

## Out of scope

- Verdict replay/re-derivation from a trace alone (O1), including carrying the declared scope
  or raw skill bytes in the trace.
- Key generation/management, ssh-agent, hardware keys, key rotation, revocation.
- Multiple signatures, Sigstore/cosign, transparency logs, timestamping.
- Registry/install-time verification, HTTP publishing, hosted verification.
- Attesting a skill directory's other files (the `Skill` docstring's project-level manifest).
- Any change to A5's verdict semantics, finding classes, or the `check` CLI contract.

## Areas to strengthen before sharing (self-critique)

- 🔴 **Replay gap (O1).** A signature over a verdict that cannot be independently re-derived
  is integrity, not proof of correctness. The PRD names it; ARCHITECTURE's current sentence
  ("a verdict re-derives from the trace and the strictness policy alone") must be corrected,
  not left to contradict the shipped code.
- 🟡 **Sandbox hash opacity.** The hash list commits to config digests a third party cannot
  expand without the original config. It proves confinement happened under *some* recorded
  configs, not which settings they were. A readable policy record is a follow-on.
- 🟡 **Key UX.** A dedicated unencrypted key is a real operational ask; the docs must say how
  to make one and why (`ssh-keygen -t ed25519 -N '' -f ~/.ssh/assay-attest`).
- 🟡 **`--skill` coupling.** Bundling requires the original `SKILL.md`; a lost skill means an
  unbundlable trace. Acceptable for now, and the hash check makes the coupling honest.
- Question before greenlighting: **should the bundle embed the trace (chosen, self-contained)
  or reference the trace file by hash (smaller, two files)?** Embedding matches
  ARCHITECTURE's "the bundle carries the trace" and removes a substitution path; it makes the
  bundle larger.
