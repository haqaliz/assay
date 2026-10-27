from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from assay.ingest import ParseCause, Scope, Skill, SkillParseError


def test_parse_cause_is_the_closed_nine_name_set():
    assert {c.name for c in ParseCause} == {
        "NOT_A_FILE",
        "TOO_LARGE",
        "NO_FRONTMATTER",
        "INVALID_UTF8",
        "INVALID_YAML",
        "DUPLICATE_KEY",
        "MISSING_NAME",
        "MISSING_DESCRIPTION",
        "INVALID_SCOPE",
    }


def test_parse_error_exposes_cause_detail_path_and_a_readable_message():
    err = SkillParseError(ParseCause.NO_FRONTMATTER, "no closing ---", Path("a/SKILL.md"))
    assert err.cause is ParseCause.NO_FRONTMATTER
    assert err.detail == "no closing ---"
    assert err.path == Path("a/SKILL.md")
    assert "a/SKILL.md" in str(err)
    assert "no closing ---" in str(err)


def test_scope_absent_key_is_none_for_every_dimension():
    scope = Scope(tools=None)
    assert scope.tools is None
    assert scope.files is None
    assert scope.network is None


def test_scope_explicitly_empty_is_empty_not_none():
    scope = Scope(tools=[], files=[], network=[])
    assert scope.tools == frozenset()
    assert scope.files == ()
    assert scope.network == ()
    assert scope.tools is not None
    assert scope.files is not None
    assert scope.network is not None


def test_scope_normalizes_to_frozenset_and_ordered_tuple():
    scope = Scope(tools=["Read", "Bash", "Read"], files=["./out/**", "report.md"])
    assert scope.tools == frozenset({"Read", "Bash"})
    assert scope.files == ("./out/**", "report.md")


def test_scope_rejects_non_string_members_instead_of_coercing():
    with pytest.raises(TypeError, match="files"):
        Scope(files=(1,))
    with pytest.raises(TypeError, match="tools"):
        Scope(tools=["Read", 2])


def test_skill_is_frozen():
    skill = Skill(
        name="demo",
        description="does a demo",
        scope=Scope(),
        body="body\n",
        source_path=Path("SKILL.md"),
        content_hash="0" * 64,
    )
    with pytest.raises(FrozenInstanceError):
        skill.name = "other"  # type: ignore[misc]
