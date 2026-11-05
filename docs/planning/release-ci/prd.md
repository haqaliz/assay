# PRD — `release-ci` (v0.1 readiness: CI, changelog, version)

Status: approved 2026-11-05 (next milestone). Date: 2026-11-05.
Pipeline position: release readiness. No tag, no PyPI publish, no version bump.

## Problem statement

The repo has 916 offline tests, a lockfile, and a complete engine, but no CI, no changelog, and no
way to ask the installed package for its version. A contributor cannot see whether a change is
green without running the suite locally; a reader cannot see what shipped; a future release has no
history to build on. The release phase is still deferred: there is no tag, no PyPI token, and no
publish workflow. This unit builds the **readiness** pieces only.

For whom: the maintainer, a contributor/CI, and the future release unit.

## Goals and success metrics

| Goal | Metric |
|---|---|
| CI runs the suite | A macOS GitHub Actions workflow runs `uv sync --frozen --dev` + `uv run pytest` on push/PR to `master` |
| The version is queryable | `assay --version` prints `assay <package version>` from installed metadata; a test pins it |
| The history exists | `CHANGELOG.md` has an `Unreleased` section covering A1–A10, replay, the corpus, the audit gate and the adapters |
| No release claim | No tag, no PyPI publish, no version bump; the version stays `0.0.1` |
| No collateral change | 916 tests unchanged; no A5/corpus/trace/bundle change; no new dependency |

## Users and scenarios

1. **Contributor** — opens a PR; the macOS CI runs the offline suite.
2. **Maintainer** — `assay --version` reports the installed version; `CHANGELOG.md` is the history.
3. **Future release** — the changelog and CI are the base for a tag/publish unit.

## Requirements

### Must have

1. **CI workflow** `.github/workflows/ci.yml`:
   - triggers on `push` to `master` and `pull_request` to `master`;
   - `permissions: contents: read`;
   - `runs-on: macos-latest` (the suite needs Seatbelt and `ssh-keygen`);
   - steps: `actions/checkout@v4`, `astral-sh/setup-uv@v5` with cache, `uv sync --frozen --dev`,
     `uv run pytest`;
   - `timeout-minutes: 20`; no secrets; no model/network calls.
2. **`assay --version`**: the top-level parser has `--version` (`action="version"`), printing
   `assay <version>` from `importlib.metadata.version("assayhq")`; no hardcoded duplicate. A test
   asserts the flag exits 0 and the output contains the metadata version. `assay check --version`
   is not required (unknown arg → 2).
3. **`CHANGELOG.md`**: `# Changelog`, an `## [Unreleased]` section with `### Added` entries for the
   shipped engine (ingest formats, sandbox, driver, capture/verdict, bundle/replay, corpus/benchmark,
   audit gate, triage) and a `### Limits` note (synthetic corpus, single labeler, no public audit,
   MCP deferred). No version heading beyond `Unreleased`.
4. **README**: a CI badge (`haqaliz/assay/actions/workflows/ci.yml`), a short `## Development`
   section (`uv sync --dev`, `uv run pytest`, `uv run assay --version`), and the version flag in
   the usage.
5. **Docs/status**: ROADMAP progress block (CI/changelog/version, 916 tests, no tag/publish);
   CLAUDE.md status line; no release claim.
6. **No tag, no PyPI publish, no version bump, no release workflow; no new dependency.**

### Should have

7. The workflow uses the committed `uv.lock` (`--frozen`) so CI is reproducible.
8. The changelog links the key PRs/commits where useful; no invented release dates beyond the
   `Unreleased` section.

### Nice to have (deferred)

A tag/publish workflow (needs a PyPI token and the name decision), a Linux job (the sandbox is
macOS-only), a release notes generator, a signed release.

## Technical considerations

- **macOS only.** The suite uses `sandbox-exec` and `ssh-keygen`; a Linux runner would fail the
  sandbox tests. A single macOS job is the honest CI for this stage.
- **Frozen lockfile.** `uv sync --frozen --dev` uses `uv.lock`; the test run is reproducible.
- **Version source.** `importlib.metadata.version("assayhq")` reads the installed distribution; the
  package name is `assayhq`, the CLI is `assay`. No second version constant.
- **No secrets.** The workflow only checks out and runs tests; no API keys, no network model calls.
- **First-run risk.** GitHub's macOS image may differ from the dev host (`sandbox-exec` is
  deprecated but present); the PR's CI run is the proof. If it fails, fix the workflow/tests before
  merging.
- **No release.** No tag, no `twine`, no PyPI token; the changelog is `Unreleased`.

## Risks and open questions

| Risk | L/I | Mitigation |
|---|---|---|
| The macOS runner lacks/changes `sandbox-exec` | Med/High | The PR CI run is the proof; fix before merge; the sandbox tests are the canary |
| CI is slow/expensive | Low/Med | One macOS job, cache, timeout 20 |
| A version constant drifts | Med/Med | Read installed metadata; no duplicate |
| The changelog over-claims a release | Med/Med | Only `Unreleased`; no tag/publish |
| The first CI run fails on a dev-only path | Med/Med | The suite skips the dogfood path; fix the workflow/tests before merge |
| Users read CI as a release | Low/Med | No tag/PyPI; README says development |

Open questions (recommendations):

- **O1 — macOS version?** [`macos-latest`; switch to a pinned image only if it breaks.]
- **O2 — a Linux job?** [No; the sandbox is macOS-only.]
- **O3 — version bump?** [No; the release unit decides.]
- **O4 — publish workflow?** [Deferred; needs a PyPI token and the name decision.]

Challenge: **does CI/changelog/version count as a milestone?** It is not a capability; it is the
infrastructure that makes the 916 tests and the history usable. The credibility milestone (M2.3)
still needs a second reviewer; this is the safe, autonomous readiness step.

## Out of scope

- Tag, PyPI publish, release workflow, version bump, signing, release notes.
- A Linux runner, a sandbox backend change.
- A5/corpus/trace/bundle changes; new dependencies.
- The M2.3 audit (needs a reviewer) and MCP (deferred).

## Areas to strengthen before sharing (self-critique)

- 🔴 **CI is not the moat.** The execution-grounded verdict remains the product; this unit only
  protects it.
- 🟡 **First-run risk.** The workflow is unproven until the PR runs on GitHub; do not merge a red CI.
- 🟡 **No release.** The changelog is `Unreleased`; a tag/PyPI unit is separate.
- 🟡 **macOS-only CI.** A Linux contributor cannot run the sandbox tests; the README says macOS.
- Question before greenlighting: **should the CI also run `uv run assay corpus corpus/` as a smoke
  test?** [Optional; the pytest suite already loads the corpora. Keep the workflow minimal.]
