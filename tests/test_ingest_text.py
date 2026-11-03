import hashlib
from pathlib import Path

import pytest

from assay.ingest import (
    MAX_SKILL_BYTES,
    ParseCause,
    SkillParseError,
    parse_skill,
    parse_skill_text,
)

SOURCE = """---
name: text-skill
description: Parsed from text.
allowed-tools: Read, Bash
metadata:
  assay:
    files:
      - out/**
    network:
      - api.example.com:443
---
# Text skill

Body stays verbatim.
"""


def _write(tmp_path: Path, raw: bytes) -> Path:
    path = tmp_path / "SKILL.md"
    path.write_bytes(raw)
    return path


def test_parse_text_and_parse_produce_the_same_skill(tmp_path):
    path = _write(tmp_path, SOURCE.encode("utf-8"))
    from_file = parse_skill(path)
    from_text = parse_skill_text(SOURCE, path)
    assert from_text == from_file
    assert from_text.content_hash == hashlib.sha256(SOURCE.encode("utf-8")).hexdigest()
    assert from_text.name == "text-skill"
    assert from_text.scope.tools == frozenset({"Read", "Bash"})
    assert from_text.scope.files == ("out/**",)
    assert from_text.scope.network == ("api.example.com:443",)


def test_parse_text_preserves_bom_and_crlf_bytes(tmp_path):
    raw = b"\xef\xbb\xbf---\r\nname: bom-crlf\r\ndescription: Keeps bytes.\r\n---\r\nBody.\r\n"
    path = _write(tmp_path, raw)
    from_text = parse_skill_text(raw.decode("utf-8"), path)
    assert from_text.content_hash == hashlib.sha256(raw).hexdigest()
    assert from_text == parse_skill(path)


@pytest.mark.parametrize("value", [SOURCE.encode("utf-8"), None], ids=["bytes", "none"])
def test_parse_text_rejects_a_non_string(value):
    with pytest.raises(SkillParseError) as caught:
        parse_skill_text(value)
    assert caught.value.cause is ParseCause.INVALID_UTF8


def test_parse_text_rejects_unencodable_text():
    with pytest.raises(SkillParseError) as caught:
        parse_skill_text("---\nname: \ud800\ndescription: d\n---\n")
    assert caught.value.cause is ParseCause.INVALID_UTF8


def test_parse_text_rejects_oversized_text():
    with pytest.raises(SkillParseError) as caught:
        parse_skill_text("x" * (MAX_SKILL_BYTES + 1))
    assert caught.value.cause is ParseCause.TOO_LARGE


def test_parse_text_rejects_malformed_frontmatter():
    with pytest.raises(SkillParseError) as caught:
        parse_skill_text("no frontmatter here\n")
    assert caught.value.cause is ParseCause.NO_FRONTMATTER


def test_parse_skill_still_returns_the_file_skill(tmp_path):
    path = _write(tmp_path, SOURCE.encode("utf-8"))
    skill = parse_skill(path)
    assert skill.name == "text-skill"
    assert skill.source_path == path
    assert skill.content_hash == hashlib.sha256(path.read_bytes()).hexdigest()
