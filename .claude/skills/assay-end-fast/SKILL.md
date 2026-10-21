---
name: assay-end-fast
description: Use when finishing local work on an Assay unit of work after the PR is merged and you want to clean up without generating a completion report. Triggers on "assay-end-fast", "aef", "aef bug 12", "aef feat skill-ingest", "end fast".
arguments: "type id"
---

# Assay End (Fast Track)

## Overview

Closes out a unit of work's local state after the PR has merged: **master → pull →
remove worktree → delete branch**, with a **release phase that is deferred until
Assay has release machinery**. No report (use `assay-end` / `ae` for that).

**Invocation:** `aef <type> <id>` — e.g. `aef bug 12`, `aef feat skill-ingest`.

- `type` ∈ `bug | feat | feature | task | chore` (normalize `feature` → `feat`)
- `id` = the GitHub issue number, or the slug used at begin time
- Owner is `aliz`
- Branch: `<type>/<id>/aliz`; worktree dir: `.claude/worktrees/<type>-<id>`

Assay's base branch is **`master`**.

## Pipeline

### Phase 0 — Safety check

- **Worktree clean?** `git -C <worktree> status --porcelain` must be empty.
- **Branch merged?** Confirm the PR is merged if reachable. `git branch -d` refuses
  an unmerged branch; don't bypass with `-D` without explicit user OK.

### Phase 1 — Main, pulled

```bash
PRIMARY=$(git worktree list | head -1 | awk '{print $1}')
git -C "$PRIMARY" checkout master
git -C "$PRIMARY" pull --ff-only origin master
```

### Phase 2 — Remove worktree, delete branch

```bash
WORKTREE_NAME="<type>-<id>"
BRANCH="<type>/<id>/aliz"

git -C "$PRIMARY" worktree remove ".claude/worktrees/$WORKTREE_NAME"
git -C "$PRIMARY" branch -d "$BRANCH"
```

Verify:

```bash
git -C "$PRIMARY" worktree list
git -C "$PRIMARY" branch --list "$BRANCH"
```

### Phase 3 — Release a new version (DEFERRED — no machinery yet)

**Assay has no release machinery today.** Cleanup ends at Phase 2. Do not
hand-craft a release, tag, or publish anything.

When release machinery lands (its own unit of work), this phase becomes
ALWAYS-run: `feat`/`feature` → minor, `bug`/`chore`/`task` → patch; bump +
changelog on `master`; CI green before tagging; tag and push to trigger the
workflow; verify each channel is live before calling it done. Release identity:
the **haqaliz** account. PyPI distribution name: `assay` is taken; `assayhq` was
free when checked — settle it in the release-machinery unit.

### Phase 4 — Comment on the issue (optional)

Ask first. Draft 2-4 sentences, no em dashes, no jargon. Confirm with the user,
then `gh issue comment "$ID" --body "<confirmed text>"`.

## Common mistakes

| Mistake | Fix |
|---|---|
| Running from inside the worktree being removed | Resolve `PRIMARY` first |
| Checking out / pulling `master` | Assay's base branch is `master` |
| Using `git pull` (allowing merge) | Use `--ff-only` |
| Forcing branch delete with `-D` | Only after explicit user OK |
| Cutting a release | Deferred — no machinery yet |
| Posting the issue comment without confirmation | Draft first, confirm, then post |
