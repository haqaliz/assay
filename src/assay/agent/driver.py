"""The bounded loop: the model runs outside the jail, every action inside it."""

from __future__ import annotations

import time
from typing import Callable

from assay.ingest import Skill

from .base import Message, Model
from .records import Budget, ModelFailed, RunCause, RunOutcome, ToolAction, Usage
from .tools import TOOLS, Toolbox


def drive(
    skill: Skill,
    task: str,
    model: Model,
    toolbox: Toolbox,
    budget: Budget,
    *,
    clock: Callable[[], float] = time.monotonic,
) -> RunOutcome:
    # shortcut: wall time is checked between calls; a single slow call is bounded by the
    # transport's 60 s timeout, not by this budget.
    started = clock()
    messages = [Message("system", skill.body), Message("user", task)]
    actions: list[ToolAction] = []
    usage = Usage()
    spent = 0.0
    steps = 0

    def outcome(cause: RunCause | None, final_text: str | None = None) -> RunOutcome:
        return RunOutcome(
            cause=cause,
            final_text=final_text,
            steps=steps,
            actions=tuple(actions),
            usage=usage,
            cost_usd=spent,
        )

    while True:
        if clock() - started > budget.max_wall_seconds:
            return outcome(RunCause.WALL_LIMIT)
        if spent >= budget.max_usd:
            return outcome(RunCause.COST_CAPPED)
        if steps >= budget.max_steps:
            return outcome(RunCause.STEP_LIMIT)

        try:
            reply = model.complete(messages, TOOLS)
        except ModelFailed:
            return outcome(RunCause.MODEL_FAILED)

        steps += 1
        spent += model.price.cost(reply.usage)
        usage = usage + reply.usage
        if spent > budget.max_usd:
            return outcome(RunCause.COST_CAPPED)
        if not reply.tool_calls:
            return outcome(None, reply.text or "")

        messages.append(Message("assistant", reply.text or "", tool_calls=reply.tool_calls))
        for tool_call in reply.tool_calls:
            result = toolbox.execute(tool_call)
            actions.append(ToolAction(call=tool_call, result=result))
            content = result.output or ("" if result.ok else f"tool {tool_call.name!r} failed")
            messages.append(Message("tool", content, tool_call_id=tool_call.id))
