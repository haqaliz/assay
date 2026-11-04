"""Cursor project rule (.mdc) ingest: frontmatter, declared file scope and identity."""

from __future__ import annotations

import hashlib
from pathlib import Path

from .claude import MAX_SKILL_BYTES, _parse_frontmatter, _read_bytes
from .records import Format, ParseCause, Scope, Skill, SkillParseError

_DEFAULT_PATH = Path("rule.mdc")


def _raw_bytes(text: str, path: Path) -> bytes:
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
    return raw


def _always_apply(mapping: dict, path: Path) -> bool:
    if "alwaysApply" not in mapping:
        return False
    value = mapping["alwaysApply"]
    if not isinstance(value, bool):
        raise SkillParseError(ParseCause.INVALID_SCOPE, "alwaysApply must be a boolean", path)
    return value


def _globs(mapping: dict, path: Path) -> tuple[str, ...] | None:
    if "globs" not in mapping:
        return None
    value = mapping["globs"]
    if isinstance(value, str):
        patterns = [pattern.strip() for pattern in value.split(",")]
        if not all(patterns):
            raise SkillParseError(
                ParseCause.INVALID_SCOPE,
                "globs has an empty entry; remove the extra comma",
                path,
            )
        return tuple(patterns)
    if isinstance(value, list) and all(
        isinstance(pattern, str) and pattern.strip() for pattern in value
    ):
        return tuple(pattern.strip() for pattern in value)
    raise SkillParseError(
        ParseCause.INVALID_SCOPE,
        "globs must be a comma-separated string or a list of non-empty strings",
        path,
    )


def _description(mapping: dict, body: str, name: str, path: Path) -> str:
    if "description" in mapping:
        value = mapping["description"]
        if not isinstance(value, str):
            raise SkillParseError(ParseCause.INVALID_SCOPE, "description must be a string", path)
        if value.strip():
            return value
    return next((line.strip() for line in body.splitlines() if line.strip()), name)


def _parse(raw: bytes, path: Path) -> Skill:
    mapping, body = _parse_frontmatter(raw, path)
    name = path.stem or "cursor-rule"
    always_apply = _always_apply(mapping, path)
    description = _description(mapping, body, name, path)
    files = ("*",) if always_apply else _globs(mapping, path)
    return Skill(
        name=name,
        description=description,
        scope=Scope(files=files),
        body=body,
        source_path=path,
        content_hash=hashlib.sha256(raw).hexdigest(),
        format=Format.CURSOR,
        requirements=(),
    )


def parse_cursor_rule(path: Path) -> Skill:
    path = Path(path)
    return _parse(_read_bytes(path), path)


def parse_cursor_text(text: str, path: Path = _DEFAULT_PATH) -> Skill:
    path = Path(path)
    return _parse(_raw_bytes(text, path), path)


def looks_like_cursor(text: str) -> bool:
    try:
        mapping, _ = _parse_frontmatter(_raw_bytes(text, _DEFAULT_PATH), _DEFAULT_PATH)
    except SkillParseError:
        return False
    return "globs" in mapping or "alwaysApply" in mapping
