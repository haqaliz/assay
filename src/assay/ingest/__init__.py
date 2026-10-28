"""Assay skill ingest: a skill is data, never executed at parse time."""

from .base import Parser
from .claude import MAX_SKILL_BYTES, ClaudeSkillParser, parse_skill
from .records import ParseCause, Scope, Skill, SkillParseError

__all__ = [
    "MAX_SKILL_BYTES",
    "ClaudeSkillParser",
    "ParseCause",
    "Parser",
    "Scope",
    "Skill",
    "SkillParseError",
    "parse_skill",
]
