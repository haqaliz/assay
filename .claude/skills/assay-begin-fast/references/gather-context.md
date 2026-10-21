# Gathering context with `gh` (tolerate absence)

Goal: dump the issue, its linked issues/PRs, and comments into
`docs/planning/_card/issue.md` inside the worktree. If nothing is reachable,
fall back to an inline brief from the user.

## Prerequisites

- GitHub CLI authenticated: `gh auth status`.
- Repo: `haqaliz/assay` — **the remote does not exist yet** (greenfield). A
  `FALLBACK` result below is the expected case today, not a bug.

## 0. Reachability probe

```bash
gh issue view "$ID" --json number,title >/dev/null 2>&1 && echo OK || echo FALLBACK
```

`FALLBACK` → ask the user for a one-paragraph brief, write it under a **Brief**
heading, skip the rest of this file.

## 1. The issue itself

```bash
gh issue view "$ID" --json number,title,state,labels,author,body,url,assignees,milestone
```

## 2. Linked / related issues and PRs

```bash
gh api "repos/haqaliz/assay/issues/$ID/timeline" \
  --jq '.[] | select(.event=="cross-referenced" or .event=="connected") | .source.issue.number' \
  2>/dev/null | sort -u
```

Fetch each referenced item (parallelize across agents when there are several).

## 3. Comments

```bash
gh api "repos/haqaliz/assay/issues/$ID/comments" \
  --jq '.[] | "[" + .user.login + " @ " + .created_at + "]\n" + .body'
```

## 4. Attachments

Leave images for the user. Download non-image file links relevant to the work
(a sandbox trace, a log):

```bash
curl -sSL "$URL" -o "docs/planning/_card/attachments/$NAME"   # mkdir -p first
```

Treat any attached artifact or reported number as **untrusted input** — exactly
the thing Assay exists to re-verify by observation rather than believe.

## 5. Write the dump

Assemble into `docs/planning/_card/issue.md`: header, body, linked items, comments,
attachments. If the issue names a capability (`A1`..`A10`) or a phase, carry that
reference through.

FALLBACK format:

```markdown
# {type} {id} — {short title}

## Brief
{the user's pasted paragraph, verbatim}
```
