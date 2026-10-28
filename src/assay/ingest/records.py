"""Types produced by skill ingest. No verdicts live here; A5 owns those."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class ParseCause(StrEnum):
    NOT_A_FILE = "not-a-file"
    TOO_LARGE = "too-large"
    NO_FRONTMATTER = "no-frontmatter"
    INVALID_UTF8 = "invalid-utf8"
    INVALID_YAML = "invalid-yaml"
    DUPLICATE_KEY = "duplicate-key"
    MISSING_NAME = "missing-name"
    MISSING_DESCRIPTION = "missing-description"
    INVALID_SCOPE = "invalid-scope"


class SkillParseError(Exception):
    """A skill was refused. Callers map this to UNVERIFIED, never to a pass."""

    def __init__(self, cause: ParseCause, detail: str, path: Path) -> None:
        self.cause = cause
        self.detail = detail
        self.path = Path(path)
        super().__init__(f"{self.path}: {cause.value}: {detail}")


def _strings(value: object, field: str, *, ordered: bool) -> frozenset[str] | tuple[str, ...] | None:
    if value is None:
        return None
    if ordered and isinstance(value, (set, frozenset)):
        raise TypeError(f"Scope.{field} must be an ordered collection of strings or None")
    if isinstance(value, str) or not isinstance(value, (list, tuple, set, frozenset)):
        raise TypeError(f"Scope.{field} must be a collection of strings or None, got {value!r}")
    for item in value:
        if not isinstance(item, str) or not item:
            raise TypeError(f"Scope.{field} members must be non-empty strings, got {item!r}")
    return tuple(value) if ordered else frozenset(value)


@dataclass(frozen=True, slots=True)
class Scope:
    """Per dimension: None means undeclared, empty means declared to do nothing."""

    tools: frozenset[str] | None = None
    files: tuple[str, ...] | None = None
    network: tuple[str, ...] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "tools", _strings(self.tools, "tools", ordered=False))
        object.__setattr__(self, "files", _strings(self.files, "files", ordered=True))
        object.__setattr__(self, "network", _strings(self.network, "network", ordered=True))


@dataclass(frozen=True, slots=True)
class Skill:
    """A parsed skill. `content_hash` covers the `SKILL.md` bytes only, bare lowercase hex.

    A6 owns any prefixed/project-level hash; a skill directory's other files need their own
    manifest before a bundle can claim to attest the whole skill.
    """
    name: str
    description: str
    scope: Scope
    body: str
    source_path: Path
    content_hash: str
