from pathlib import Path

import pytest

from assay.ingest import ParseCause, SkillParseError, parse_skill
from assay.ingest.claude import MAX_SKILL_BYTES, _parse_frontmatter

FIXTURES = Path(__file__).parent / "fixtures" / "skills"


def _refuses(path: Path, cause: ParseCause) -> None:
    with pytest.raises(SkillParseError) as caught:
        _parse_frontmatter(path.read_bytes(), path)
    assert caught.value.cause is cause, caught.value


def test_minimal_fixture_splits_mapping_and_body():
    path = FIXTURES / "minimal" / "SKILL.md"
    mapping, body = _parse_frontmatter(path.read_bytes(), path)
    assert mapping == {"name": "minimal", "description": "A minimal skill."}
    assert body == "# Minimal\n\nBody line.\n"


def test_bom_and_crlf_twins_parse_the_same_and_keep_their_body_bytes():
    plain = FIXTURES / "plain" / "SKILL.md"
    bom = FIXTURES / "bom" / "SKILL.md"
    crlf = FIXTURES / "crlf" / "SKILL.md"
    expected, _ = _parse_frontmatter(plain.read_bytes(), plain)
    assert _parse_frontmatter(bom.read_bytes(), bom)[0] == expected
    assert _parse_frontmatter(crlf.read_bytes(), crlf)[0] == expected
    assert _parse_frontmatter(crlf.read_bytes(), crlf)[1] == "# Plain\r\n\r\nBody.\r\n"


def test_unquoted_plain_scalar_with_a_colon_space_is_repaired_not_refused():
    path = FIXTURES / "unquoted_colon" / "SKILL.md"
    mapping, _ = _parse_frontmatter(path.read_bytes(), path)
    assert mapping["description"] == (
        "Use when deciding something. Triggers: unquoted-colon, colon test."
    )
    assert mapping["allowed-tools"] == "Read, Grep"
    assert mapping["metadata"] == {"owner": "someone"}


def test_comments_and_multiline_quoted_scalars_are_left_to_strict_yaml(tmp_path):
    path = tmp_path / "SKILL.md"
    path.write_bytes(
        b'---\nname: n\nallowed-tools: Read, Write # allow: all\n'
        b'description: "first line\nsecond: line"\n---\n'
    )
    mapping, _ = _parse_frontmatter(path.read_bytes(), path)
    assert mapping["allowed-tools"] == "Read, Write"
    assert mapping["description"] == "first line second: line"


@pytest.mark.parametrize(
    ("fixture", "cause"),
    [
        ("no_frontmatter", ParseCause.NO_FRONTMATTER),
        ("unclosed", ParseCause.NO_FRONTMATTER),
        ("list_root", ParseCause.INVALID_YAML),
        ("duplicate_key", ParseCause.DUPLICATE_KEY),
    ],
)
def test_fixture_refusals(fixture, cause):
    _refuses(FIXTURES / fixture / "SKILL.md", cause)


def test_non_utf8_bytes_are_named(tmp_path):
    path = tmp_path / "SKILL.md"
    path.write_bytes(b"---\nname: \xff\n---\n")
    _refuses(path, ParseCause.INVALID_UTF8)


def test_oversized_file_is_refused_before_reading(tmp_path, monkeypatch):
    path = tmp_path / "SKILL.md"
    path.write_bytes(b"x" * (MAX_SKILL_BYTES + 1))
    monkeypatch.setattr(Path, "read_bytes", lambda self: pytest.fail("read_bytes must not run"))
    with pytest.raises(SkillParseError) as caught:
        parse_skill(path)
    assert caught.value.cause is ParseCause.TOO_LARGE


def test_duplicate_nested_key_is_refused(tmp_path):
    path = tmp_path / "SKILL.md"
    path.write_bytes(b"---\nmetadata:\n  a: 1\n  a: 2\n---\n")
    _refuses(path, ParseCause.DUPLICATE_KEY)


def test_invalid_yaml_syntax_is_named(tmp_path):
    path = tmp_path / "SKILL.md"
    path.write_bytes(b"---\nname: [unclosed\n---\n")
    _refuses(path, ParseCause.INVALID_YAML)
