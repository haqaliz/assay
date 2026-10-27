from pathlib import Path

import pytest

from assay.ingest import SkillParseError, parse_skill

PLUMB = Path.home() / "dev/at/plumb/.claude/skills"
INSTALLED = Path.home() / ".claude/skills"


def _corpus(root: Path) -> list[Path]:
    if not root.is_dir():
        pytest.skip(f"dogfood corpus not present: {root}")
    paths = sorted(root.glob("*/SKILL.md"))
    if not paths:
        pytest.skip(f"no skills under {root}")
    return paths


def test_plumb_skills_parse_and_match_their_directory():
    for path in _corpus(PLUMB):
        assert parse_skill(path).name == path.parent.name, path


def test_installed_skills_parse_or_refuse_with_a_named_cause():
    for path in _corpus(INSTALLED):
        try:
            parse_skill(path)
        except SkillParseError:
            pass
