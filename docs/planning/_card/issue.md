# feat release-ci — v0.1 readiness: CI, changelog, version

## Brief

Make the repo ready to be treated as a v0.1 project without cutting a release: a macOS GitHub
Actions workflow that runs the offline suite, a `CHANGELOG.md` with an `Unreleased` section, and
`assay --version` from the installed package metadata. No tag, no PyPI publish, no version bump; the
release phase stays deferred. The workflow is read-only and needs no secrets.

Source: the `assay-end-fast` release phase ("no release machinery today; do not hand-craft a
release"), the 916-test suite, and the absence of `.github/`, `CHANGELOG.md` and a version flag.

## Context carried from the pick

- 916 offline tests pass locally; the suite needs macOS (`sandbox-exec`) and `ssh-keygen`.
- `pyproject.toml` is version `0.0.1`, distribution `assayhq`; no CI, no changelog, no `--version`.
- The release identity is `haqaliz`; the PyPI name is unsettled (`assay` taken, `assayhq` free when
  checked). This unit does not publish.
- No new dependency; no A5/corpus/trace/bundle change.
