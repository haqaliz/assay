import json
from pathlib import Path

import pytest

from assay.ingest import Format, ParseCause, Scope, Skill, SkillParseError, parse_skill_text

PATH = Path("openclaw/SKILL.md")


def _source(frontmatter: str) -> str:
    return f"---\n{frontmatter.strip()}\n---\n# Body\n"


def _skill_record(**overrides) -> Skill:
    fields = {
        "name": "demo",
        "description": "does a demo",
        "scope": Scope(),
        "body": "body\n",
        "source_path": Path("SKILL.md"),
        "content_hash": "0" * 64,
    }
    fields.update(overrides)
    return Skill(**fields)


def test_openclaw_skill_is_detected_with_requirements():
    skill = parse_skill_text(
        _source(
            """
name: gemini
description: Generate images with the Gemini CLI.
metadata: {openclaw: {emoji: "♊", requires: {bins: [uv], env: [GEMINI_API_KEY], config: [browser.enabled]}}}
"""
        ),
        PATH,
    )
    assert skill.format is Format.OPENCLAW
    assert skill.requirements == ("bin:uv", "env:GEMINI_API_KEY", "config:browser.enabled")


def test_openclaw_any_bins_and_os():
    skill = parse_skill_text(
        _source(
            """
name: search
description: Search with ripgrep or grep.
metadata:
  openclaw:
    requires:
      anyBins: [rg, grep]
    os: [linux, macos]
"""
        ),
        PATH,
    )
    assert skill.format is Format.OPENCLAW
    assert skill.requirements == ("any-bin:grep,rg", "os:linux,macos")


def test_openclaw_ignores_non_requirement_metadata():
    skill = parse_skill_text(
        _source(
            """
name: gemini
description: Generate images with the Gemini CLI.
metadata:
  openclaw:
    always: true
    emoji: "♊"
    homepage: https://example.com/gemini
    install:
      - kind: brew
        formula: uv
    primaryEnv: GEMINI_API_KEY
    skillKey: gemini
    requires:
      unknown: [nope]
"""
        ),
        PATH,
    )
    assert skill.format is Format.OPENCLAW
    assert skill.requirements == ()


def test_openclaw_block_without_requires_is_still_openclaw():
    skill = parse_skill_text(
        _source(
            """
name: hello
description: Says hello.
metadata:
  openclaw: {}
"""
        ),
        PATH,
    )
    assert skill.format is Format.OPENCLAW
    assert skill.requirements == ()


def test_claude_skill_is_unchanged():
    skill = parse_skill_text(
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
        PATH,
    )
    assert skill.format is Format.CLAUDE_CODE
    assert skill.requirements == ()
    assert skill.scope.tools == frozenset({"Read", "Bash"})
    assert skill.scope.files == ("out/**", "report.md")
    assert skill.scope.network == ("api.example.com:443",)


def test_openclaw_and_assay_metadata_can_coexist():
    skill = parse_skill_text(
        _source(
            """
name: gemini
description: Generate images with the Gemini CLI.
metadata:
  assay:
    files: [out/**]
    network: [api.example.com:443]
  openclaw:
    requires:
      bins: [uv]
"""
        ),
        PATH,
    )
    assert skill.format is Format.OPENCLAW
    assert skill.requirements == ("bin:uv",)
    assert skill.scope.files == ("out/**",)
    assert skill.scope.network == ("api.example.com:443",)


@pytest.mark.parametrize("openclaw", ["[1]", "nope", "3"])
def test_openclaw_metadata_must_be_a_mapping(openclaw):
    text = _source(f"name: x\ndescription: y\nmetadata: {{openclaw: {openclaw}}}")
    with pytest.raises(SkillParseError) as caught:
        parse_skill_text(text, PATH)
    assert caught.value.cause is ParseCause.INVALID_SCOPE
    assert "metadata.openclaw" in caught.value.detail


@pytest.mark.parametrize("requires", ["requires: nope", "requires: [bins]", "requires: 3"])
def test_openclaw_requires_must_be_a_mapping(requires):
    text = _source(f"name: x\ndescription: y\nmetadata:\n  openclaw:\n    {requires}")
    with pytest.raises(SkillParseError) as caught:
        parse_skill_text(text, PATH)
    assert caught.value.cause is ParseCause.INVALID_SCOPE
    assert "metadata.openclaw.requires" in caught.value.detail


@pytest.mark.parametrize("field", ["bins", "anyBins", "env", "config", "os"])
@pytest.mark.parametrize("value", ["uv", ["uv", 3], ["uv", ""], ["uv", " "]])
def test_openclaw_requirement_fields_must_be_lists_of_non_empty_strings(field, value):
    if field == "os":
        block = f"  openclaw:\n    os: {json.dumps(value)}\n"
    else:
        block = f"  openclaw:\n    requires:\n      {field}: {json.dumps(value)}\n"
    text = _source("name: x\ndescription: y\nmetadata:\n" + block)
    with pytest.raises(SkillParseError) as caught:
        parse_skill_text(text, PATH)
    assert caught.value.cause is ParseCause.INVALID_SCOPE
    assert field in caught.value.detail


def test_openclaw_os_must_not_be_empty():
    text = _source("name: x\ndescription: y\nmetadata:\n  openclaw:\n    os: []\n")
    with pytest.raises(SkillParseError) as caught:
        parse_skill_text(text, PATH)
    assert caught.value.cause is ParseCause.INVALID_SCOPE
    assert "os" in caught.value.detail


def test_skill_rejects_an_unknown_requirement_prefix():
    with pytest.raises(ValueError, match="bad:x"):
        _skill_record(requirements=("bad:x",))


def test_skill_accepts_all_requirement_prefixes():
    requirements = ("bin:ls", "any-bin:ls,cat", "env:X", "config:a.b", "os:darwin")
    skill = _skill_record(requirements=requirements)
    assert skill.requirements == requirements


def test_skill_rejects_a_non_format_value():
    with pytest.raises(TypeError, match="Format"):
        _skill_record(format="openclaw")
