"""MCP server identity and the stdio manifest parser (Stage A)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path


class ServerError(ValueError):
    """A server manifest was refused. The message never includes env values."""


@dataclass(frozen=True, slots=True)
class Server:
    name: str
    command: str
    args: tuple[str, ...]
    source_path: Path
    source_hash: str
    transport: str = "stdio"


def parse_server(path: Path, *, name: str | None = None) -> Server:
    path = Path(path)
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ServerError(f"{path}: cannot read manifest: {exc}") from None
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ServerError(f"{path}: manifest is not UTF-8: {exc}") from None
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ServerError(f"{path}: invalid JSON: {exc.msg}") from None
    if not isinstance(payload, dict):
        raise ServerError(f"{path}: manifest root must be an object")

    if "mcpServers" in payload:
        entries = payload["mcpServers"]
        if not isinstance(entries, dict):
            raise ServerError(f"{path}: mcpServers must be an object")
        if not entries:
            raise ServerError(f"{path}: no servers in mcpServers")
        names = ", ".join(sorted(entries))
        if name is None:
            if len(entries) != 1:
                raise ServerError(f"{path}: multiple servers; choose --name ({names})")
            selected = next(iter(entries))
        else:
            if name not in entries:
                raise ServerError(f"{path}: server {name!r} not found ({names})")
            selected = name
        entry = entries[selected]
    else:
        selected = name or path.stem
        if not selected:
            raise ServerError(f"{path}: server name is empty")
        entry = payload

    if not isinstance(entry, dict):
        raise ServerError(f"{path}: server {selected!r} must be an object")
    if "url" in entry:
        raise ServerError(f"{path}: stdio only; url is not supported")
    env = entry.get("env")
    if env is not None:
        if not isinstance(env, dict):
            raise ServerError(f"{path}: env must be an object")
        if env:
            raise ServerError(
                f"{path}: env values are not supported; no secrets in the jail"
            )
    command = entry.get("command")
    if not isinstance(command, str) or not command:
        raise ServerError(f"{path}: command must be a non-empty string")
    args = entry.get("args", [])
    if not isinstance(args, list) or any(not isinstance(arg, str) for arg in args):
        raise ServerError(f"{path}: args must be a list of strings")

    return Server(
        name=selected,
        command=command,
        args=tuple(args),
        source_path=path,
        source_hash=hashlib.sha256(raw).hexdigest(),
    )
