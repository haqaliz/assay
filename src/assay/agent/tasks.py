"""One deterministic task per skill; multiple tasks belong to a later slice."""

from __future__ import annotations

from assay.ingest import Skill


def task_for(skill: Skill) -> str:
    return (
        f"Carry out the skill {skill.name!r}: {skill.description}\n\n"
        "Use the provided tools to do its real work. If it needs input, choose a small example "
        "and create whatever files you need in the run directory. Do not just describe the work: "
        "perform it.\n\n"
        "When you are done, finish with a short summary of what you did and what you produced.\n"
    )
