from pathlib import Path

from assay.agent.tasks import task_for
from assay.ingest import Scope, Skill


def skill(**over):
    base = dict(
        name="report-writer",
        description="Writes a small report from the files it is given.",
        scope=Scope(),
        body="Read the inputs, then write report.md.\n",
        source_path=Path("report-writer/SKILL.md"),
        content_hash="0" * 64,
    )
    base.update(over)
    return Skill(**base)


def test_task_is_identical_for_the_same_skill():
    assert task_for(skill()) == task_for(skill())


def test_task_names_the_skill_and_its_purpose():
    task = task_for(skill())
    assert "report-writer" in task
    assert "Writes a small report from the files it is given." in task


def test_task_carries_the_skill_instructions():
    assert "Read the inputs, then write report.md." in task_for(skill())


def test_task_asks_for_a_small_example_tools_and_a_summary():
    task = task_for(skill()).lower()
    assert "small example" in task
    assert "tools" in task
    assert "summary" in task
