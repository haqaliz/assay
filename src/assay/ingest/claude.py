"""Claude Code SKILL.md ingest: frontmatter, declared scope and identity."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import yaml

from .records import Format, ParseCause, Scope, Skill, SkillParseError

MAX_SKILL_BYTES = 1_000_000

_TOP_LEVEL_KEY_VALUE = re.compile(r"^([A-Za-z0-9_.-]+):[ \t]+(.+?)[ \t]*$")
_YAML_INDICATORS = "{['\"|>&*!%@`#"


def _repair_plain_scalars(frontmatter: str) -> str:
    """Quote top-level plain scalars containing ': ', which YAML forbids but Claude Code accepts.

    Only invoked after strict YAML has refused the file, so a valid declaration is never rewritten.
    shortcut: only single-line top-level values are repaired; a nested multiline bad value still
    refuses as INVALID_YAML.
    """
    repaired: list[str] = []
    for line in frontmatter.splitlines(keepends=True):
        core = line.rstrip("\r\n")
        eol = line[len(core) :]
        match = _TOP_LEVEL_KEY_VALUE.match(core)
        if match and ": " in match.group(2) and match.group(2)[0] not in _YAML_INDICATORS:
            value = match.group(2).replace("\\", "\\\\").replace('"', '\\"')
            core = f'{match.group(1)}: "{value}"'
        repaired.append(core + eol)
    return "".join(repaired)


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
    if isinstance(value, list):
        names = [item.strip() for item in value if isinstance(item, str)]
        if len(names) != len(value) or not all(names):
            raise SkillParseError(
                ParseCause.INVALID_SCOPE,
                "allowed-tools list must contain only non-empty strings",
                path,
            )
        return frozenset(names)
    if not isinstance(value, str) or not value.strip():
        raise SkillParseError(
            ParseCause.INVALID_SCOPE,
            "allowed-tools must be a non-empty comma-separated string or a list of strings",
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
    return tuple(item.strip() for item in value)


def _openclaw_strings(mapping: dict, key: str, field: str, path: Path) -> list[str]:
    if key not in mapping:
        return []
    value = mapping[key]
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise SkillParseError(
            ParseCause.INVALID_SCOPE,
            f"{field} must be a list of non-empty strings",
            path,
        )
    return sorted(item.strip() for item in value)


def _format_and_requirements(mapping: dict, path: Path) -> tuple[Format, tuple[str, ...]]:
    metadata = mapping.get("metadata")
    if not isinstance(metadata, dict) or "openclaw" not in metadata:
        return Format.CLAUDE_CODE, ()
    openclaw = metadata["openclaw"]
    if not isinstance(openclaw, dict):
        raise SkillParseError(
            ParseCause.INVALID_SCOPE, "metadata.openclaw must be a mapping", path
        )
    requirements: list[str] = []
    if "requires" in openclaw:
        requires = openclaw["requires"]
        if not isinstance(requires, dict):
            raise SkillParseError(
                ParseCause.INVALID_SCOPE, "metadata.openclaw.requires must be a mapping", path
            )
        requirements.extend(
            f"bin:{name}"
            for name in _openclaw_strings(
                requires, "bins", "metadata.openclaw.requires.bins", path
            )
        )
        any_bins = _openclaw_strings(
            requires, "anyBins", "metadata.openclaw.requires.anyBins", path
        )
        if any_bins:
            requirements.append("any-bin:" + ",".join(any_bins))
        requirements.extend(
            f"env:{name}"
            for name in _openclaw_strings(
                requires, "env", "metadata.openclaw.requires.env", path
            )
        )
        requirements.extend(
            f"config:{name}"
            for name in _openclaw_strings(
                requires, "config", "metadata.openclaw.requires.config", path
            )
        )
    if "os" in openclaw:
        os_names = _openclaw_strings(openclaw, "os", "metadata.openclaw.os", path)
        if not os_names:
            raise SkillParseError(
                ParseCause.INVALID_SCOPE,
                "metadata.openclaw.os must be a non-empty list of non-empty strings",
                path,
            )
        requirements.append("os:" + ",".join(os_names))
    return Format.OPENCLAW, tuple(requirements)


def _load_yaml(frontmatter: str, path: Path) -> dict:
    try:
        return _load_yaml_once(frontmatter, path)
    except _InvalidYaml:
        try:
            return _load_yaml_once(_repair_plain_scalars(frontmatter), path)
        except _InvalidYaml as exc:
            raise SkillParseError(ParseCause.INVALID_YAML, str(exc), path) from None


class _InvalidYaml(Exception):
    """Internal: retry once with the de-facto repair before refusing."""


def _load_yaml_once(frontmatter: str, path: Path) -> dict:
    loader = None
    try:
        loader = _UniqueKeyLoader(frontmatter)
        loader.path = path
        data = loader.get_single_data()
    except SkillParseError:
        raise
    except (yaml.YAMLError, TypeError, RecursionError) as exc:
        raise _InvalidYaml(f"frontmatter is not valid YAML: {exc}") from None
    finally:
        if loader is not None:
            loader.dispose()
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise _InvalidYaml(f"frontmatter root must be a mapping, got {type(data).__name__}")
    return data


def _required_text(mapping: dict, key: str, cause: ParseCause, path: Path) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise SkillParseError(cause, f"{key} must be a non-empty string", path)
    return value


def _read_bytes(path: Path) -> bytes:
    try:
        if not path.is_file():
            raise SkillParseError(ParseCause.NOT_A_FILE, "skill path must be a regular file", path)
        size = path.stat().st_size
        if size > MAX_SKILL_BYTES:
            raise SkillParseError(
                ParseCause.TOO_LARGE, f"file is {size} bytes; the limit is {MAX_SKILL_BYTES}", path
            )
        return path.read_bytes()
    except SkillParseError:
        raise
    except OSError as exc:
        raise SkillParseError(ParseCause.NOT_A_FILE, f"cannot read {path}: {exc}", path) from None


class ClaudeSkillParser:
    def parse(self, path: Path) -> Skill:
        path = Path(path)
        return self._parse(_read_bytes(path), path)

    def parse_text(self, text: str, path: Path = Path("SKILL.md")) -> Skill:
        path = Path(path)
        if not isinstance(text, str):
            raise SkillParseError(ParseCause.INVALID_UTF8, "skill source must be text", path)
        try:
            raw = text.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise SkillParseError(
                ParseCause.INVALID_UTF8, f"skill source is not valid UTF-8: {exc}", path
            ) from None
        if len(raw) > MAX_SKILL_BYTES:
            raise SkillParseError(
                ParseCause.TOO_LARGE,
                f"file is {len(raw)} bytes; the limit is {MAX_SKILL_BYTES}",
                path,
            )
        return self._parse(raw, path)

    def _parse(self, raw: bytes, path: Path) -> Skill:
        path = Path(path)
        mapping, body = _parse_frontmatter(raw, path)
        scope = _scope(mapping, path)
        skill_format, requirements = _format_and_requirements(mapping, path)
        return Skill(
            name=_required_text(mapping, "name", ParseCause.MISSING_NAME, path),
            description=_required_text(
                mapping, "description", ParseCause.MISSING_DESCRIPTION, path
            ),
            scope=scope,
            body=body,
            source_path=path,
            content_hash=hashlib.sha256(raw).hexdigest(),
            format=skill_format,
            requirements=requirements,
        )


def parse_skill(path: Path) -> Skill:
    return ClaudeSkillParser().parse(path)


def parse_skill_text(text: str, path: Path = Path("SKILL.md")) -> Skill:
    return ClaudeSkillParser().parse_text(text, path)
