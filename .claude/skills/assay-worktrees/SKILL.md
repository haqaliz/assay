---
name: assay-worktrees
description: Isolate parallel work in the Assay repo using the Claude Code worktree layout. Use when starting a new bug/feature that should not collide with another running Claude session. Covers branch naming, worktree placement under .claude/worktrees, per-worktree uv setup, and cleanup.
allowed-tools: Bash, Read, Write, Edit, Glob
---

# Assay Worktree Workflow

## When to Use

- Another Claude session is running on a different branch in Assay and you want to
  start a new bug/feature without colliding.
- You want to run two branches side by side.
- The primary checkout is dirty and switching branches would mix work.

Don't use this for one-off file edits that finish in a single session.

## Layout — the official Claude Code pattern

Assay is a **single repo**. Worktrees live **inside it** at `.claude/worktrees/<name>/`.
`.claude/worktrees/` is already in `.gitignore`.

```
/Users/aliz/dev/at/assay/                                    ← primary (main)
/Users/aliz/dev/at/assay/.claude/worktrees/bug-12/           ← bug #12 worktree
/Users/aliz/dev/at/assay/.claude/worktrees/feat-skill-ingest/
```

Verify ignore status any time: `git check-ignore -v '.claude/worktrees/'` (keep the
trailing slash — a bare `.claude/worktrees` reports "not ignored" when the directory
doesn't exist yet, which is a false alarm, not a missing rule).

## Branch naming convention

`<type>/<id>/<owner>` — owner is `aliz`. `id` is a GitHub issue number when there is
one, otherwise a short descriptive slug.

- `bug/12/aliz`
- `feat/skill-ingest/aliz`
- `chore/pin-uv-version/aliz`

Worktree dir name drops the slashes: `<type>-<id>` (e.g. `bug-12`, `feat-skill-ingest`).

## The base branch is `main`

Assay's base branch is **`main`**. The remote is `git@github.com:haqaliz/assay.git`
once it exists — **it does not exist yet** (greenfield, local-only repo). Branch from
local `main` until a remote is created, then prefer `origin/main`:

```bash
# today: no remote yet
git worktree add -b feat/skill-ingest/aliz .claude/worktrees/feat-skill-ingest main

# once a remote exists
git fetch origin main
git worktree add -b feat/skill-ingest/aliz .claude/worktrees/feat-skill-ingest origin/main
```

## Creating a worktree

```bash
# from an existing branch you already pushed
git worktree add .claude/worktrees/feat-skill-ingest feat/skill-ingest/aliz

# via Claude Code's --worktree flag
claude --worktree feat-skill-ingest
```
The `--worktree` flag names the branch `worktree-feat-skill-ingest`, which won't match
your issue/slug naming — create the branch first, then `git worktree add` with it.

## Auto-copying gitignored config (`.worktreeinclude`)

No secrets/env files exist yet — the repo is docs-only. Once a `.env` exists for BYOK
keys, create `.worktreeinclude` and list it, then copy manually for bare `git worktree
add` (the include only runs via `claude --worktree`):

```bash
cp .env .claude/worktrees/feat-skill-ingest/   # only once such a file exists
```

**Never copy captured sandbox traces, findings, or corpus cases between worktrees.**
They are run state tied to the run that produced them.

## Per-worktree setup (Python core — uv)

```bash
cd .claude/worktrees/feat-skill-ingest
uv sync
uv run pytest
uv run assay --help
```

⚠️ **Greenfield caveat:** no `pyproject.toml`, no `uv.lock`, no `src/` yet. `uv sync`
fails until the Python core is scaffolded. If your work *is* the scaffolding, the
failing test comes first. Skip this section for docs-only work.

## Switching between worktrees

```bash
git -C /Users/aliz/dev/at/assay worktree list
```

## Cleaning up

```bash
git -C /Users/aliz/dev/at/assay worktree remove .claude/worktrees/feat-skill-ingest
git -C /Users/aliz/dev/at/assay branch -d feat/skill-ingest/aliz
```

## Common pitfalls

| Symptom | Cause | Fix |
|---|---|---|
| `invalid reference: origin/main` | Remote not fetched, or doesn't exist yet | Branch from local `main` until a remote exists |
| Branching from `master` | Assay's base branch is `main` | Use `main` |
| Worktree contents appear untracked in primary | `.claude/worktrees/` not ignored | Already in `.gitignore`; verify with trailing slash |
| `uv sync` fails: no `pyproject.toml` | Core not scaffolded (greenfield) | Expected — scaffold it test-first, or skip for docs-only work |
| `git worktree add` fails: "already checked out" | Branch checked out elsewhere | `git checkout main` in the conflicting worktree, retry |
