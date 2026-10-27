"""Claude Code SKILL.md ingest: frontmatter, declared scope and identity."""

from __future__ import annotations

from pathlib import Path

import yaml

from .records import ParseCause, SkillParseError

MAX_SKILL_BYTES = 1_000_000


class _UniqueKeyLoader(yaml.SafeLoader):
    """SafeLoader that refuses a repeated key at any depth instead of silently keeping one."""

    path: Path

    def construct_mapping(self, node: yaml.MappingNode, deep: bool = False) -> dict:
        seen: set[object] = set()
        for key_node, _ in node.value:
            key = self.construct_object(key_node, deep=deep)
            if key in seen:
                raise SkillParseError(
                    ParseCause.DUPLICATE_KEY, f"duplicate key {key!r} in frontmatter", self.path
                )
            seen.add(key)
        return super().construct_mapping(node, deep=deep)


def _parse_frontmatter(raw: bytes, path: Path) -> tuple[dict, str]:
    if not path.is_file():
        raise SkillParseError(ParseCause.NOT_A_FILE, "skill path must be a regular file", path)
    if len(raw) > MAX_SKILL_BYTES:
        raise SkillParseError(
            ParseCause.TOO_LARGE,
            f"file is {len(raw)} bytes; the limit is {MAX_SKILL_BYTES}",
            path,
        )
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SkillParseError(ParseCause.INVALID_UTF8, f"file is not valid UTF-8: {exc}", path) from None
    frontmatter, body = _split_frontmatter(text, path)
    return _load_yaml(frontmatter, path), body


def _split_frontmatter(text: str, path: Path) -> tuple[str, str]:
    text = text.removeprefix("\ufeff")
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\r\n") != "---":
        raise SkillParseError(ParseCause.NO_FRONTMATTER, 'file must start with a "---" line', path)
    for i, line in enumerate(lines[1:], 1):
        if line.rstrip("\r\n") == "---":
            return "".join(lines[1:i]), "".join(lines[i + 1 :])
    raise SkillParseError(
        ParseCause.NO_FRONTMATTER, 'frontmatter has no closing "---" line', path
    )


def _load_yaml(frontmatter: str, path: Path) -> dict:
    loader = _UniqueKeyLoader(frontmatter)
    loader.path = path
    try:
        data = loader.get_single_data()
    except SkillParseError:
        raise
    except (yaml.YAMLError, TypeError) as exc:
        raise SkillParseError(
            ParseCause.INVALID_YAML, f"frontmatter is not valid YAML: {exc}", path
        ) from None
    finally:
        loader.dispose()
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise SkillParseError(
            ParseCause.INVALID_YAML,
            f"frontmatter root must be a mapping, got {type(data).__name__}",
            path,
        )
    return data
