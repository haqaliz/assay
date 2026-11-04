"""Assay skill ingest: a skill is data, never executed at parse time."""

from .base import Parser
from .claude import MAX_SKILL_BYTES, ClaudeSkillParser, parse_skill, parse_skill_text
from .records import Format, ParseCause, Scope, Skill, SkillParseError

__all__ = [
    "MAX_SKILL_BYTES",
    "ClaudeSkillParser",
    "Format",
    "ParseCause",
    "Parser",
    "Scope",
    "Skill",
    "SkillParseError",
    "parse_skill",
    "parse_skill_text",
]
