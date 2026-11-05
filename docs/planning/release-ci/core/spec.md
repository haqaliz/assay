# Spec — `release-ci` / `core` (v0.1 readiness)

## Problem slice & user outcome

A macOS GitHub Actions workflow runs the offline suite on every push/PR to `master`; `assay
--version` reports the installed package version; `CHANGELOG.md` has an `Unreleased` history. No
tag, PyPI publish or version bump. The contributor sees a green check; the maintainer sees the
history; the future release has a base.

## In scope

- `.github/workflows/ci.yml`.
- `assay --version` (top-level parser, metadata version) + test.
- `CHANGELOG.md` (`Unreleased`).
- README CI badge, `## Development`, version flag; ROADMAP/CLAUDE status.
- No new dependency; no A5/corpus/trace/bundle change.

## Out of scope

Tag, PyPI publish, release workflow, version bump, signing, release notes; a Linux job; a sandbox
backend change; the M2.3 audit; MCP.

## CI workflow

```yaml
name: CI
on:
  push:
    branches: [master]
  pull_request:
    branches: [master]
permissions:
  contents: read
jobs:
  test:
    runs-on: macos-latest
    timeout-minutes: 20
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
        with:
          enable-cache: true
      - run: uv sync --frozen --dev
      - run: uv run pytest
```

- The suite is offline; no secrets. The macOS runner provides `sandbox-exec` and `ssh-keygen`.
- `--frozen` uses the committed `uv.lock`.
- The workflow runs on the PR; the first run is the proof. Do not merge a red CI.

## Version

- `build_parser()` adds `parser.add_argument("--version", action="version", version=f"assay
  {version('assayhq')}")`, where `version` is `importlib.metadata.version` (imported locally or at
  module top).
- No second hardcoded version; `pyproject.toml` stays `0.0.1`.
- A test in `tests/test_cli_args.py`: `main(["--version"])` raises `SystemExit(0)`, stdout contains
  `assay <importlib.metadata.version("assayhq")>`, and no traceback.
- `assay check --version` remains an unknown arg (exit 2); not required.

## Changelog

`CHANGELOG.md`:
- `# Changelog`, a one-line purpose.
- `## [Unreleased]` with `### Added`:
  - ingest for Claude Code `SKILL.md`, OpenClaw/ClawHub `SKILL.md`, Cursor `.mdc`; format/requirements/file scope;
  - macOS Seatbelt sandbox; BYOK agent driver (Anthropic + OpenAI-compatible/local);
  - capture/diff; verdict/strictness/floor;
  - signed bundle schema 2 + replay; 20-case corpus/benchmark + 8-case held-out + 8-case real control;
  - audit gate (`ETHICS.md`, protocol, template); static pre-filter (`assay triage`); CI/changelog/version.
- `### Limits`: synthetic/single-labeler corpus; no public audit; MCP deferred; A9 deferred;
  `SKILL.md`/`.mdc` only, not the whole directory.
- No version heading beyond `Unreleased`; no tag/publish claim.

## README / status

- CI badge: `https://github.com/haqaliz/assay/actions/workflows/ci.yml/badge.svg` (branch `master`).
- `## Development`: `uv sync --dev`, `uv run pytest`, `uv run assay --version`; macOS note.
- Usage: `assay --version`.
- ROADMAP progress block: v0.1 readiness (CI/changelog/version), 916 tests, no tag/publish; the
  engine capability roadmap is complete for A1–A8 (file-based) and A10; A9/MCP deferred.
- CLAUDE.md status: CI runs the offline suite on macOS; `assay --version`; no release tag/publish.

## Acceptance criteria

1. The workflow file is valid YAML, triggers on push/PR to `master`, has read-only permissions,
   runs `uv sync --frozen --dev` and `uv run pytest` on `macos-latest`.
2. `assay --version` prints the installed metadata version and exits 0; the test passes.
3. `CHANGELOG.md` has `## [Unreleased]` with the shipped capabilities and the limits; no version
   heading/tag/publish claim.
4. README has the CI badge, `## Development`, and the version flag; ROADMAP/CLAUDE are synced.
5. `uv run pytest` is green locally (916 + the version test); no A5/corpus/trace/bundle change.
6. The PR's CI run is green before merge. If it fails on the macOS runner, fix the workflow/tests
   first.

## Dependencies & sequencing

The existing suite and lockfile. Order: version flag/test → workflow/changelog → docs → push → CI →
merge.

## Risks

- The GitHub macOS image may differ (`sandbox-exec` deprecated); the PR run is the proof.
- The version metadata name is `assayhq`; the CLI is `assay`.
- No release: the changelog is `Unreleased`.
- macOS-only CI; no Linux job.
