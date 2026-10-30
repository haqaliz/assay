"""The bounded loop: the model runs outside the jail, every action inside it."""

from __future__ import annotations

import time
from typing import Callable

from assay.ingest import Skill
from assay.sandbox import SandboxFailed, SandboxUnavailable

from .base import Message, Model
from .records import Budget, ModelFailed, RunCause, RunOutcome, ToolAction, Usage
from .tools import TOOLS, Toolbox

MAX_TOOL_CONTENT_CHARS = 16_000


def _estimate_input_tokens(messages: list[Message]) -> int:
    """Conservative: four characters per token, arguments included."""
    chars = sum(len(message.content) for message in messages)
    chars += sum(len(str(call.arguments)) for message in messages for call in message.tool_calls)
    return max(1, chars // 4)


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
        if steps >= budget.max_steps:
            return outcome(RunCause.STEP_LIMIT)
        # Refuse a call whose worst case would cross the cap before spending it (R5).
        estimate = model.price.cost(
            Usage(_estimate_input_tokens(messages), model.max_tokens)
        )
        if spent + estimate > budget.max_usd:
            return outcome(RunCause.COST_CAPPED)

        try:
            reply = model.complete(messages, TOOLS)
        except ModelFailed:
            return outcome(RunCause.MODEL_FAILED)

        steps += 1
        spent += model.price.cost(reply.usage)
        usage = usage + reply.usage
        if spent > budget.max_usd:
            return outcome(RunCause.COST_CAPPED)
        if clock() - started > budget.max_wall_seconds:
            return outcome(RunCause.WALL_LIMIT)
        if not reply.tool_calls:
            return outcome(None, reply.text or "")

        messages.append(Message("assistant", reply.text or "", tool_calls=reply.tool_calls))
        for tool_call in reply.tool_calls:
            if len(actions) >= budget.max_actions:
                return outcome(RunCause.ACTION_LIMIT)
            if clock() - started > budget.max_wall_seconds:
                return outcome(RunCause.WALL_LIMIT)
            try:
                result = toolbox.execute(tool_call)
            except (SandboxUnavailable, SandboxFailed):
                return outcome(RunCause.SANDBOX_UNAVAILABLE)
            actions.append(ToolAction(call=tool_call, result=result))
            content = result.output[:MAX_TOOL_CONTENT_CHARS]
            if len(result.output) > MAX_TOOL_CONTENT_CHARS:
                content += "\n...[truncated]"
            if not content:
                content = "ok" if result.ok else f"tool {tool_call.name!r} failed"
            messages.append(Message("tool", content, tool_call_id=tool_call.id))
