---
name: assay-report
description: Use when an Assay unit of work (bug, task, feature) is done and you want a brief, friendly, non-technical completion note saved on Desktop to share with the team.
allowed-tools: Read, Grep, Glob, Bash, Write
arguments: "type id"
---

# Assay Completion Note

A short, friendly, non-technical heads-up that a unit of work is done.

## Arguments

- `type` ∈ `bug | task | feature`
- `id` = the GitHub issue number, or the slug used at begin time

Usage: `/assay-report bug 12` or `/assay-report feature skill-ingest`.

## Output

Markdown file saved to `/Users/aliz/Desktop/{type}-{id}-completion.md`.

## The template

```markdown
## #{id} - {Feature or area} - {Short Title}

Hey! Quick note that this one's {verb}.

**What changed (in plain words):**
{One or two friendly sentences. No jargon. No em dashes.}

**See it live:** {link to the PR, or the CLI command}
**Screenshot/video:** {attached, or link}

If anything looks off or you'd like a tweak, just say the word.
```

Verb per type: `bug → fixed`, `task → done`, `feature → shipped`.

## Tone rules

- Plain English. Swap *declared scope, observed behavior, sandbox, capture, diff,
  finding, verdict, bundle, content-addressed* for everyday phrasing. "Runs the
  skill and checks it only does what it says" beats "execution-grounded
  declared-vs-observed diffing."
- No checklists, no commit hashes, no file paths.
- **Never use the em dash character `—`.**

## Don't over-claim (this one matters here)

- Don't say a skill is "safe" when the verdict is `CLEAN` — say the observed run
  matched what it claimed, this time.
- Don't imply `MALICIOUS` without saying it was reproduced, captured behavior —
  never an accusation based on how a skill reads.
- If the work is a slice of a bigger capability, say it's a first step.

## Workflow

1. **Get the context.** `gh issue view "$ID"` or `gh pr view "$PR"`, or write from
   the session's own work if neither resolves.
2. **Distill** into one or two plain sentences.
3. **Pick the "See it live" target**: the merged PR, or the exact CLI command
   (`uv run assay check <skill>`).
4. **Ask for a screenshot or short video** if one isn't on hand.
5. **Write** the note and tell the user it's ready.

## Example (feature)

```markdown
## #34 - Scanner - Check a skill before you install it

Hey! Quick note that this one's shipped.

**What changed (in plain words):**
Assay can now run a skill in a locked-down sandbox and watch exactly what it
does, then check that against what it claims to do. If it tries something it
never mentioned, that gets flagged instead of slipping through quietly.

**See it live:** run `uv run assay check <skill>` and watch the verdict
**Screenshot/video:** attached

If anything looks off or you'd like a tweak, just say the word.
```
