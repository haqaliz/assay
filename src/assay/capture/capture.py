"""Turn one agent run into a trace. No verdicts live here; A5 owns those."""

from __future__ import annotations

import hashlib
import ipaddress
import posixpath
from pathlib import Path, PurePath
from urllib.parse import urlsplit

from assay.agent import RunOutcome, ToolAction
from assay.ingest import Skill
from assay.sandbox import RunRecord

from .records import CaptureError, Event, EventKind, EventOutcome, Trace

EXCERPT_BYTES = 4096

_TOOL_KINDS = {
    "read_file": EventKind.FILE_READ,
    "write_file": EventKind.FILE_WRITE,
    "http_get": EventKind.NETWORK,
    "run_shell": EventKind.SHELL,
}


def capture(skill: Skill, task: str, outcome: RunOutcome) -> Trace:
    try:
        events = tuple(_event(action) for action in outcome.actions)
        if outcome.steps > 0:
            events += (_instruction("system", skill.body), _instruction("user", task))
        return Trace(
            skill_name=skill.name,
            skill_content_hash=skill.content_hash,
            task_sha256=_digest(task),
            cause=outcome.cause.value if outcome.cause is not None else None,
            input_tokens=outcome.usage.input_tokens,
            output_tokens=outcome.usage.output_tokens,
            cost_usd=outcome.cost_usd,
            events=events,
        )
    except UnicodeError as exc:
        raise CaptureError(f"trace text is not valid unicode: {exc}") from None


def _event(action: ToolAction) -> Event:
    record = action.result.record
    kind = _TOOL_KINDS.get(action.call.name, EventKind.TOOL)
    raw_url = _argument(action, "url")
    if kind is EventKind.FILE_READ or kind is EventKind.FILE_WRITE:
        target = _path(_argument(action, "path"), record)
    elif kind is EventKind.NETWORK:
        target = _network_target(raw_url)
    elif kind is EventKind.SHELL:
        target = _argument(action, "command") or action.call.name
    else:
        target = action.call.name
    content = (
        record.stdout + record.stderr if record is not None else action.result.output
    )
    written = _argument(action, "content") if kind is EventKind.FILE_WRITE else None
    return Event(
        kind=kind,
        outcome=_outcome(record),
        target=target,
        content_sha256=_digest(content),
        content_bytes=len(content.encode("utf-8")),
        excerpt=_excerpt(content),
        input_sha256=_digest(written) if written is not None else None,
        request=raw_url if kind is EventKind.NETWORK else None,
        denials=tuple(f"{denial.kind.value}: {denial.detail}" for denial in record.denials)
        if record is not None
        else (),
        truncated=record.truncated if record is not None else False,
    )


def _outcome(record: RunRecord | None) -> EventOutcome:
    if record is None:
        return EventOutcome.FAILED
    if record.ok:
        return EventOutcome.OK
    return EventOutcome.DENIED if record.denials else EventOutcome.FAILED


def _instruction(target: str, text: str) -> Event:
    return Event(
        kind=EventKind.INSTRUCTION,
        outcome=EventOutcome.OK,
        target=target,
        content_sha256=_digest(text),
        content_bytes=len(text.encode("utf-8")),
        excerpt=_excerpt(text),
    )


def _argument(action: ToolAction, name: str) -> str | None:
    value = action.call.arguments.get(name)
    return value if isinstance(value, str) else None


def _network_target(url: str) -> str:
    try:
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            return url
    except ValueError:
        return url
    return _host_port(url)


def _host_port(value: str) -> str:
    """A URL or a declared host[:port] becomes canonical lowercase host:port."""
    try:
        parts = urlsplit(value)
        if parts.hostname is None:
            parts = urlsplit(f"//{value}")
        if parts.hostname is None:
            return value
        port = (
            parts.port
            if parts.port is not None
            else 443
            if parts.scheme == "https"
            else 80
            if parts.scheme == "http"
            else 443
        )
    except ValueError:
        return value
    host = _canonical_host(parts.hostname)
    return f"{host}:{port}"


def _canonical_host(host: str) -> str:
    host = host.lower().rstrip(".")
    try:
        return str(ipaddress.ip_address(host))
    except ValueError:
        return host


def _path(raw: str | None, record: RunRecord | None) -> str:
    if raw is None:
        return ""
    normal = posixpath.normpath(raw)
    if record is None:
        return normal
    root = Path(record.run_root)
    # shortcut: this resolves against the live run root when it still exists. If a caller deleted
    # the root first, the lexical path is recorded and an escaping symlink could hide.
    if not root.is_dir():
        if PurePath(normal).is_absolute():
            try:
                return PurePath(normal).relative_to(PurePath(record.run_root)).as_posix()
            except ValueError:
                return normal
        return normal
    candidate = Path(normal) if PurePath(normal).is_absolute() else root / normal
    try:
        resolved = candidate.resolve()
        base = root.resolve()
    except (OSError, ValueError):
        return normal
    try:
        resolved.relative_to(base)
    except ValueError:
        return resolved.as_posix()
    return resolved.relative_to(base).as_posix() or "."


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _excerpt(text: str) -> str:
    return text.encode("utf-8")[:EXCERPT_BYTES].decode("utf-8", "ignore")
