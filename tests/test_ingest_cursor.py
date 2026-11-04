import hashlib
from pathlib import Path

import pytest

from assay.ingest import (
    Format,
    ParseCause,
    SkillParseError,
    looks_like_cursor,
    parse_cursor_rule,
    parse_cursor_text,
    parse_skill,
    parse_skill_text,
)

PATH = Path(".cursor/rules/rule.mdc")


def _source(frontmatter: str, body: str = "# Body\n") -> str:
    return f"---\n{frontmatter.strip()}\n---\n{body}"


def test_always_apply_maps_to_all_files():
    text = _source(
        """
alwaysApply: true
globs: 3
""",
        "# Always\n\nKeep responses short.\n",
    )
    skill = parse_cursor_text(text, PATH)
    assert skill.format is Format.CURSOR
    assert skill.scope.files == ("*",)
    assert skill.requirements == ()
    assert skill.description == "# Always"
    assert skill.body == "# Always\n\nKeep responses short.\n"
    assert skill.content_hash == hashlib.sha256(text.encode("utf-8")).hexdigest()
    assert skill.source_path == PATH


def test_globs_string_is_split_and_trimmed():
    skill = parse_cursor_text(
        _source(
            """
description: TypeScript and docs.
globs: "src/**/*.ts, docs/**/*.md"
alwaysApply: false
"""
        )
    )
    assert skill.scope.files == ("src/**/*.ts", "docs/**/*.md")
    assert skill.scope.tools is None
    assert skill.scope.network is None


def test_globs_list_is_accepted():
    skill = parse_cursor_text(
        _source(
            """
description: TypeScript and docs.
globs:
  - " src/**/*.ts "
  - docs/**/*.md
"""
        )
    )
    assert skill.scope.files == ("src/**/*.ts", "docs/**/*.md")


def test_description_only_rule_has_no_file_scope():
    skill = parse_cursor_text(
        _source(
            """
description: Explains the project conventions.
alwaysApply: false
"""
        )
    )
    assert skill.scope.files is None


def test_description_falls_back_to_the_first_body_line():
    skill = parse_cursor_text(
        _source(
            """
alwaysApply: false
""",
            "\nWrite short paragraphs.\n",
        )
    )
    assert skill.description == "Write short paragraphs."


def test_name_is_the_file_stem(tmp_path):
    path = tmp_path / "style-guide.mdc"
    path.write_text(
        _source("description: House style.\n", "Be terse.\n"), encoding="utf-8"
    )
    assert parse_cursor_rule(path).name == "style-guide"


def test_missing_description_and_body_falls_back_to_the_stem():
    skill = parse_cursor_text(
        _source("alwaysApply: true\n", ""), Path(".cursor/rules/empty-rule.mdc")
    )
    assert skill.description == "empty-rule"


def test_parse_skill_dispatches_mdc_by_suffix(tmp_path):
    path = tmp_path / "typescript.mdc"
    path.write_text(
        _source("description: TypeScript rules.\nglobs: src/**/*.ts\n"), encoding="utf-8"
    )
    skill = parse_skill(path)
    assert skill.format is Format.CURSOR
    assert skill.source_path == path
    assert skill.scope.files == ("src/**/*.ts",)


def test_parse_skill_text_detects_cursor_markers():
    globs = parse_skill_text(_source("globs: src/**/*.ts\n"), PATH)
    assert globs.format is Format.CURSOR
    always_apply = parse_skill_text(_source("alwaysApply: true\n"), PATH)
    assert always_apply.format is Format.CURSOR
    explicit = parse_skill_text(
        _source("description: No marker keys here.\n"),
        PATH,
        format=Format.CURSOR,
    )
    assert explicit.format is Format.CURSOR
    claude = parse_skill_text(
        _source("name: demo\ndescription: A Claude skill.\n"), Path("SKILL.md")
    )
    assert claude.format is Format.CLAUDE_CODE


def test_parse_skill_text_rejects_a_non_format_hint():
    with pytest.raises(TypeError):
        parse_skill_text(
            _source("name: demo\ndescription: A Claude skill.\n"),
            Path("SKILL.md"),
            format="cursor",
        )


def test_cursor_rule_requires_frontmatter():
    with pytest.raises(SkillParseError) as caught:
        parse_cursor_text("Just markdown, no frontmatter.\n", PATH)
    assert caught.value.cause is ParseCause.NO_FRONTMATTER


@pytest.mark.parametrize(
    "frontmatter",
    [
        "description: 3",
        "description: [a]",
        "alwaysApply: 1",
        "alwaysApply: 'true'",
        "globs: 3",
        "globs: [src/**, 3]",
        "globs: 'src/**, ,docs/**'",
        "globs: [src/**, '']",
        "globs: [src/**, ' ']",
    ],
)
def test_bad_description_always_apply_and_globs_are_invalid_scope(frontmatter):
    with pytest.raises(SkillParseError) as caught:
        parse_cursor_text(_source(frontmatter), PATH)
    assert caught.value.cause is ParseCause.INVALID_SCOPE


def test_looks_like_cursor():
    assert looks_like_cursor(_source("globs: src/**/*.ts\n"))
    assert looks_like_cursor(_source("alwaysApply: true\n"))
    assert not looks_like_cursor(_source("name: demo\ndescription: A skill.\n"))
    assert not looks_like_cursor("no frontmatter\n")
    assert not looks_like_cursor("---\nglobs: [\n---\n")
    assert not looks_like_cursor("---\nglobs: src/**\n")


def test_claude_and_openclaw_are_unchanged(tmp_path):
    claude_path = tmp_path / "SKILL.md"
    claude_path.write_text(
        _source(
            """
name: scope-declared
description: Declares tools, files and network.
allowed-tools: Read, Bash
metadata:
  assay:
    files: [out/**, report.md]
    network: [api.example.com:443]
"""
        ),
        encoding="utf-8",
    )
    claude = parse_skill(claude_path)
    assert claude.format is Format.CLAUDE_CODE
    assert claude.scope.tools == frozenset({"Read", "Bash"})
    assert claude.scope.files == ("out/**", "report.md")

    openclaw = parse_skill_text(
        _source(
            """
name: gemini
description: Generate images with the Gemini CLI.
metadata: {openclaw: {requires: {bins: [uv]}}}
"""
        ),
        Path("openclaw/SKILL.md"),
    )
    assert openclaw.format is Format.OPENCLAW
    assert openclaw.requirements == ("bin:uv",)
