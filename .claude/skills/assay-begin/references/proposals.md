# Phase A — Diagrams & proposal PDFs

Runs after the PRD approval gate. Everything is written inside the worktree under
`docs/planning/{slug}/`.

## 1. Diagrams (`excalidraw`)

Typical set for Assay:

| Diagram | When to include |
|---|---|
| System / architecture | Almost always — where the change lives in ingest → sandbox → capture → diff → verdict → bundle |
| Data flow | A skill moves through parsing, sandboxed execution, and captured events |
| Sequence | A multi-step interaction (agent driver runs a task, a tool call is intercepted, a finding fires) |
| State machine | A verdict transition changes (`CLEAN`/`FLAGGED`/`MALICIOUS`/`UNVERIFIED`) |

Save sources to `docs/planning/{slug}/diagrams/`.

**Every text element must set `fontFamily: 2` (Helvetica).**

**Diagram the verdict honestly.** Keep the four states distinct; never draw a
static scan or model deciding `MALICIOUS` or `CLEAN` — only the observed sandbox
run decides.

## 2. Export to SVG (`excalidraw-to-svg`)

Batch-export the whole `diagrams/` directory.

## 3. Write the two proposals

In `docs/planning/{slug}/proposals/`, relative SVG paths (`../diagrams/architecture.svg`).

### `<type>-<id>-technical-proposal.md`

- Summary, current state, proposed design (embed SVGs), data/interface changes
  (finding schema, sandbox config, bundle contract, verdict contract), risks and
  trade-offs, effort/sequencing (reference the `A`-capability), open questions.

### `<type>-<id>-non-technical-proposal.md`

- The problem in plain language, what we'll do, why it matters (skill authors,
  registries, agent users who need to know a skill does only what it claims),
  what changes for users, timeline, risks.

Don't claim Assay proves more than it checked: if a finding can only reach
`UNVERIFIED`, say so plainly.

## 4. Convert to PDF (`md-to-pdf`)

```bash
cd docs/planning/{slug}/proposals
PUPPETEER_EXECUTABLE_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  md-to-pdf <type>-<id>-technical-proposal.md --basedir ..
PUPPETEER_EXECUTABLE_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  md-to-pdf <type>-<id>-non-technical-proposal.md --basedir ..
```

Verify before the gate: render a page and inspect it.

```bash
pdftoppm -png -r 70 -f 1 -l 1 <type>-<id>-technical-proposal.pdf /tmp/check
```

## 5. Approval gate

Present both PDFs and stop. Only after explicit approval continue to `tech-plan`.
