---
name: Feature request
about: Propose a capability that strengthens execution-grounded verification
title: "[feat] "
labels: enhancement
---

## The problem

<!-- The user problem or gap, ideally from a run you tried. -->

## What you would like

<!-- The capability, and how you imagine using it. -->

## Roadmap and fit

<!-- Is this already in docs/ROADMAP.md or docs/technical/CAPABILITY_ROADMAP.md? -->

Assay's rule is that execution decides: a sandboxed, observed run is the verdict. A static scan, a
manifest, or a model opinion is never a verdict above `UNVERIFIED`. How does this strengthen that
chain rather than replace it?

- [ ] It does not add a static-only or model-only verdict.
- [ ] It does not lower the four-class severity floor or raise the instruction `REVIEW` cap.
- [ ] It does not need a new dependency without justification.
- [ ] It does not require real secrets or user data in the sandbox.

## Alternatives considered

<!-- Workarounds, smaller versions, or related tools. -->
