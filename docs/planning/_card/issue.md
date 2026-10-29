# feat agent-driver — A3: Agent driver (BYOK)

## Brief

> Build A3, the agent driver, for Phase 1 milestone M1.1 in `docs/ROADMAP.md`: a user-supplied
> BYOK API key drives a real agent against synthetic tasks generated from a parsed skill's declared
> behavior, with per-run and per-session cost caps enforced before and during the run. Every file,
> shell and network action the agent takes passes through Assay's own executor and therefore runs
> inside the A2 sandbox; the model API call itself happens outside the jail. The driver sits behind
> an injectable seam so tests run offline against recorded responses, with a deterministic
> scripted-harness mode as the cost-free fallback (R5). A3 returns a run outcome (task, transcript,
> actions executed, usage/cost, named cause); it does not assign a verdict and does not own the
> trace format (A4) or the CLI (M1.4). Refuse to run without a key: no key, no subscription
> automation (R6). Acceptance: a fake model client drives the full task loop offline; a cost cap
> stops the run at the cap and yields a named `COST_CAPPED` cause; an undeclared-behavior task that
> tries to write outside the run root is denied by the sandbox and recorded as a denial, never as
> a pass; a missing key is a named refusal.

Source: chosen by `assay-next` and the merged A1 work as the only unblocked capability after A1+A2
(`docs/technical/CAPABILITY_ROADMAP.md` A3, depends on A1+A2; Phase 0 gate needs A3+A4).

## Context carried from the pick

- `docs/ROADMAP.md` M1.1: *"A user-supplied key drives an agent in the sandbox against synthetic
  tasks; cost cap enforced"*. Phase 0 gate: *"one real skill run end to end, with an observed
  behavior that differs from a declared one."*
- `docs/technical/CAPABILITY_ROADMAP.md` A3: *"Run a real agent inside the sandbox with the skill
  loaded, against synthetic tasks generated from the skill's declared behavior. Cost caps."*
  Guardrail: *"BYOK only; no consumer-subscription automation"*.
- `docs/technical/ARCHITECTURE.md`: *"Tests run offline. The agent driver sits behind an injectable
  seam; CI uses recorded traces. No model call and no network in any test."* — and
  *"UNVERIFIED causes (draft): … AGENT_FAILED, COST_CAPPED, NO_TRIGGER …"*.
- `docs/planning/sandbox-jail/understanding.md` finding 3: full event capture is A4's job and needs
  a **mediated tool surface** (the agent's calls pass through Assay's executor), not syscall
  tracing.
- `CLAUDE.md` constraint 3: shell / network / file / injected-instruction findings are the floor;
  A3 must make each class reachable (the tool set must include shell, file and network actions).
- `docs/ROADMAP.md` R5 (cost) and R6 (subscription terms) are the two risks this slice retires or
  bounds.
- Shipped dependencies: A1 `src/assay/ingest/` (tri-state `Scope`), A2 `src/assay/sandbox/`
  (`Sandbox.run(argv, config) -> RunRecord`, port-scoped network, run root, denial classification).
