"""Claude Code SKILL.md ingest: frontmatter, declared scope and identity."""

from __future__ import annotations

import hashlib
from pathlib import Path

import yaml

from .records import ParseCause, Scope, Skill, SkillParseError

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


def _scope(mapping: dict, path: Path) -> Scope:
    tools = _tools(mapping, path)
    if "metadata" not in mapping:
        return Scope(tools=tools)
    metadata = mapping["metadata"]
    if not isinstance(metadata, dict):
        raise SkillParseError(
            ParseCause.INVALID_SCOPE, "metadata must be a mapping", path
        )
    if "assay" not in metadata:
        return Scope(tools=tools)
    assay = metadata["assay"]
    if not isinstance(assay, dict):
        raise SkillParseError(
            ParseCause.INVALID_SCOPE, "metadata.assay must be a mapping", path
        )
    return Scope(
        tools=tools,
        files=_scope_list(assay, "files", path),
        network=_scope_list(assay, "network", path),
    )


def _tools(mapping: dict, path: Path) -> frozenset[str] | None:
    if "allowed-tools" not in mapping:
        return None
    value = mapping["allowed-tools"]
    if not isinstance(value, str) or not value.strip():
        raise SkillParseError(
            ParseCause.INVALID_SCOPE,
            'allowed-tools must be a non-empty comma-separated string',
            path,
        )
    names = [name.strip() for name in value.split(",")]
    if not all(names):
        raise SkillParseError(
            ParseCause.INVALID_SCOPE,
            "allowed-tools has an empty entry; remove the extra comma",
            path,
        )
    return frozenset(names)


def _scope_list(assay: dict, key: str, path: Path) -> tuple[str, ...] | None:
    if key not in assay:
        return None
    value = assay[key]
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise SkillParseError(
            ParseCause.INVALID_SCOPE,
            f"metadata.assay.{key} must be a list of non-empty strings",
            path,
        )
    return tuple(value)


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


def _required_text(mapping: dict, key: str, cause: ParseCause, path: Path) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise SkillParseError(cause, f"{key} must be a non-empty string", path)
    return value


def _read_bytes(path: Path) -> bytes:
    if not path.is_file():
        raise SkillParseError(ParseCause.NOT_A_FILE, "skill path must be a regular file", path)
    size = path.stat().st_size
    if size > MAX_SKILL_BYTES:
        raise SkillParseError(
            ParseCause.TOO_LARGE, f"file is {size} bytes; the limit is {MAX_SKILL_BYTES}", path
        )
    return path.read_bytes()


class ClaudeSkillParser:
    def parse(self, path: Path) -> Skill:
        path = Path(path)
        raw = _read_bytes(path)
        mapping, body = _parse_frontmatter(raw, path)
        return Skill(
            name=_required_text(mapping, "name", ParseCause.MISSING_NAME, path),
            description=_required_text(
                mapping, "description", ParseCause.MISSING_DESCRIPTION, path
            ),
            scope=_scope(mapping, path),
            body=body,
            source_path=path,
            content_hash=hashlib.sha256(raw).hexdigest(),
        )


def parse_skill(path: Path) -> Skill:
    return ClaudeSkillParser().parse(path)
