import hashlib
from pathlib import Path

import pytest

from assay.ingest import (
    ClaudeSkillParser,
    ParseCause,
    Parser,
    SkillParseError,
    parse_skill,
)

FIXTURES = Path(__file__).parent / "fixtures" / "skills"


def test_parse_skill_returns_a_complete_record():
    path = FIXTURES / "scope_declared" / "SKILL.md"
    skill = parse_skill(path)
    assert skill.name == "scope-declared"
    assert skill.description == "Declares tools, files and network."
    assert skill.scope.tools == frozenset({"Read", "Bash"})
    assert skill.scope.files == ("out/**", "report.md")
    assert skill.scope.network == ("api.example.com:443",)
    assert skill.body == "# Scope declared\n\nBody stays verbatim.\n"
    assert skill.source_path == path


def test_content_hash_is_sha256_of_raw_bytes():
    path = FIXTURES / "scope_declared" / "SKILL.md"
    assert parse_skill(path).content_hash == hashlib.sha256(path.read_bytes()).hexdigest()


def test_content_hash_is_stable_and_changes_with_one_byte(tmp_path):
    raw = (FIXTURES / "scope_declared" / "SKILL.md").read_bytes()
    one = tmp_path / "one.md"
    one.write_bytes(raw)
    assert parse_skill(one).content_hash == parse_skill(one).content_hash
    two = tmp_path / "two.md"
    two.write_bytes(raw + b"x")
    assert parse_skill(two).content_hash != parse_skill(one).content_hash


def test_empty_declarations_survive_the_full_parse():
    skill = parse_skill(FIXTURES / "scope_empty" / "SKILL.md")
    assert skill.scope.files == ()
    assert skill.scope.network == ()
    assert skill.scope.tools is None


def test_claude_parser_satisfies_the_parser_protocol():
    assert isinstance(ClaudeSkillParser(), Parser)


def test_parse_skill_refuses_with_the_named_error():
    with pytest.raises(SkillParseError) as caught:
        parse_skill(FIXTURES / "no_frontmatter" / "SKILL.md")
    assert type(caught.value) is SkillParseError
    assert caught.value.cause is ParseCause.NO_FRONTMATTER


@pytest.mark.parametrize(
    ("fixture", "cause"),
    [
        ("missing_name", ParseCause.MISSING_NAME),
        ("name_not_string", ParseCause.MISSING_NAME),
        ("empty_name", ParseCause.MISSING_NAME),
        ("missing_description", ParseCause.MISSING_DESCRIPTION),
    ],
)
def test_name_and_description_are_required_strings(fixture, cause):
    with pytest.raises(SkillParseError) as caught:
        parse_skill(FIXTURES / fixture / "SKILL.md")
    assert caught.value.cause is cause


def test_unknown_extras_are_tolerated_by_the_full_parse():
    path = FIXTURES / "extras" / "SKILL.md"
    skill = parse_skill(path)
    assert skill.name == "extras"
    assert skill.scope.tools == frozenset({"Read"})
