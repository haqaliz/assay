# feat openclaw-adapter — A8 first format adapter

## Brief

Add OpenClaw/ClawHub `SKILL.md` support to ingest. Detect `metadata.openclaw`, record the skill as
`Format.OPENCLAW`, and parse its declared requirements (`metadata.openclaw.requires.bins`,
`anyBins`, `env`, `config`, and `os`) into a tuple on the `Skill`. `assay check` refuses with
`UNVERIFIED/REQUIREMENTS_UNMET` before any model or sandbox call when the jail cannot satisfy a
declared requirement (`env`, `config`, a mismatched `os`, or a required binary absent from the jail
PATH); a satisfiable skill runs normally. The check report adds `format` and `requirements` to the
human and JSON output. Claude Code behavior is unchanged, the trace/bundle/corpus remain schema 2,
and there is no new dependency or A5 change.

Source: `docs/technical/CAPABILITY_ROADMAP.md` A8 and `docs/ROADMAP.md` M2.4, first adapter in the
documented order. OpenClaw format grounded in `https://docs.openclaw.ai/tools/skills` and
`https://docs.openclaw.ai/clawhub` (2026-11-05): a `SKILL.md` with YAML frontmatter, optional
`metadata.openclaw` gating, and no file/network/tool scope.

## Context carried from the pick

- `src/assay/ingest/claude.py` parses the common `SKILL.md` shape and ignores `metadata.openclaw`.
- `Skill` has no format or requirements field; the CLI cannot tell whether an OpenClaw skill can run
  in the jail.
- The jail env is `{"PATH": "/usr/bin:/bin:/usr/sbin:/sbin", **config.env}` and `config.env={}` in
  the agent toolbox; an OpenClaw skill declaring `requires.env` can never get that secret.
- The sandbox is macOS Seatbelt only; `os` requirements other than `darwin` cannot run.
- Constraints: no real secrets; execution decides; `UNVERIFIED` is not a pass; no consumer
  subscription; no new dependency.
