"""Malformed input must always leave through SkillParseError, never a bare exception."""

import os
from pathlib import Path

import pytest

from assay.ingest import ParseCause, SkillParseError, parse_skill

FIXTURES = Path(__file__).parent / "fixtures" / "skills"


def _write(tmp_path: Path, raw: bytes) -> Path:
    path = tmp_path / "SKILL.md"
    path.write_bytes(raw)
    return path


@pytest.mark.parametrize(
    ("raw", "cause"),
    [
        (b"---\nname: n\x00\ndescription: d\n---\n", ParseCause.INVALID_YAML),
        (b"---\nname: n\x0b\ndescription: d\n---\n", ParseCause.INVALID_YAML),
        (
            b"---\nname: " + b"[" * 600 + b"]" * 600 + b"\ndescription: d\n---\n",
            ParseCause.INVALID_YAML,
        ),
        (b"---\nname: n\ndescription: d\n---\n" + b"x" * 2_000_000, ParseCause.TOO_LARGE),
    ],
    ids=["control-byte", "vertical-tab", "deep-nesting", "oversized"],
)
def test_pathological_frontmatter_is_a_named_refusal(tmp_path, raw, cause):
    with pytest.raises(SkillParseError) as caught:
        parse_skill(_write(tmp_path, raw))
    assert caught.value.cause is cause


def test_directory_is_refused_by_parse_skill(tmp_path):
    with pytest.raises(SkillParseError) as caught:
        parse_skill(tmp_path)
    assert caught.value.cause is ParseCause.NOT_A_FILE


def test_fifo_is_refused_by_parse_skill(tmp_path):
    fifo = tmp_path / "SKILL.md"
    os.mkfifo(fifo)
    with pytest.raises(SkillParseError) as caught:
        parse_skill(fifo)
    assert caught.value.cause is ParseCause.NOT_A_FILE


@pytest.mark.skipif(os.geteuid() == 0, reason="root can read a mode-0 file")
def test_unreadable_file_is_refused_by_parse_skill(tmp_path):
    path = _write(tmp_path, (FIXTURES / "minimal" / "SKILL.md").read_bytes())
    path.chmod(0)
    try:
        with pytest.raises(SkillParseError) as caught:
            parse_skill(path)
        assert caught.value.cause is ParseCause.NOT_A_FILE
    finally:
        path.chmod(0o600)
