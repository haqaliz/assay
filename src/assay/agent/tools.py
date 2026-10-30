"""The mediated tool surface: one `Sandbox.run` per model tool call."""

from __future__ import annotations

import ipaddress
import shutil
import socket
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence
from urllib.parse import urlsplit

from assay.sandbox import (
    JailConfig,
    NetRule,
    SandboxFailed,
    SandboxUnavailable,
)
from assay.sandbox.base import Sandbox

from .records import AgentUnavailable, ToolCall, ToolResult

MAX_TOOL_PAYLOAD_BYTES = 1_000_000
CURL = Path("/usr/bin/curl")
CP = "/bin/cp"
SSL_DIR = Path("/private/etc/ssl")


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    description: str
    input_schema: Mapping[str, object]


def _spec(name: str, description: str, properties: Mapping[str, object]) -> ToolSpec:
    return ToolSpec(
        name=name,
        description=description,
        input_schema={
            "type": "object",
            "properties": properties,
            "required": list(properties),
        },
    )


TOOLS: tuple[ToolSpec, ...] = (
    _spec(
        "read_file",
        "Read a text file. Paths are relative to the run directory and may be absolute.",
        {"path": {"type": "string", "description": "File to read."}},
    ),
    _spec(
        "write_file",
        "Write a text file. Paths are relative to the run directory and may be absolute.",
        {
            "path": {"type": "string", "description": "File to write."},
            "content": {"type": "string", "description": "Complete file content."},
        },
    ),
    _spec(
        "run_shell",
        "Run a shell command in the sandbox, with no network access.",
        {"command": {"type": "string", "description": "Shell command to run."}},
    ),
    _spec(
        "http_get",
        "Fetch a URL with curl from inside the sandbox.",
        {"url": {"type": "string", "description": "http or https URL to fetch."}},
    ),
)

_REQUIRED = {
    "read_file": ("path",),
    "write_file": ("path", "content"),
    "run_shell": ("command",),
    "http_get": ("url",),
}

_NETWORK = (NetRule("*", 80), NetRule("*", 443))


class _InvalidArguments(Exception):
    pass


class Toolbox:
    """Executes model tool calls inside one shared, per-run jail root."""

    def __init__(self, sandbox: Sandbox, run_root: Path) -> None:
        root = Path(run_root)
        if not root.is_dir() or root.is_symlink():
            raise SandboxUnavailable(f"run_root must be an existing real directory, got {root}")
        if not CURL.exists():
            raise AgentUnavailable(f"missing-tool: curl not found at {CURL}")
        self.sandbox = sandbox
        self.run_root = root.resolve()
        # Staged payloads live outside the run root: the child can write its root, so a
        # child-created symlink there could redirect a parent-side write onto the host.
        self.io_root = Path(tempfile.mkdtemp(prefix="assay-io-")).resolve()

    def close(self) -> None:
        shutil.rmtree(self.io_root, ignore_errors=True)

    def __enter__(self) -> "Toolbox":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def execute(self, call: ToolCall) -> ToolResult:
        staged: Path | None = None
        try:
            try:
                argv, staged, reads = self._plan(call)
            except _InvalidArguments as exc:
                return ToolResult(ok=False, output=str(exc))
            config = JailConfig(
                run_root=self.run_root,
                allow_network=_NETWORK if call.name == "http_get" else (),
                allow_read_extra=reads,
                env={},
                keep=True,
            )
            # A jail that cannot be established means nothing trustworthy ran; let it abort the
            # run instead of reporting a mere tool failure.
            record = self.sandbox.run(argv, config)
            output = record.stdout if record.ok else record.stdout + record.stderr
            return ToolResult(record.ok, _capped(output), record)
        finally:
            if staged is not None:
                staged.unlink(missing_ok=True)

    def _plan(self, call: ToolCall) -> tuple[Sequence[str], Path | None, tuple[Path, ...]]:
        required = _REQUIRED.get(call.name)
        if required is None:
            raise _InvalidArguments(f"unknown tool: {call.name!r}")
        args = {name: _string_arg(call, name) for name in required}

        if call.name == "read_file":
            return ["/bin/cat", "--", args["path"]], None, ()
        if call.name == "write_file":
            content = args["content"]
            if len(content.encode("utf-8")) > MAX_TOOL_PAYLOAD_BYTES:
                raise _InvalidArguments(
                    f"write_file: content exceeds {MAX_TOOL_PAYLOAD_BYTES} bytes"
                )
            staged = self._stage(content)
            return [CP, "--", str(staged), args["path"]], staged, (self.io_root,)
        if call.name == "run_shell":
            return ["/bin/sh", "-c", args["command"]], None, ()
        return _http_argv(args["url"]), None, ((SSL_DIR,) if SSL_DIR.exists() else ())

    def _stage(self, content: str) -> Path:
        with tempfile.NamedTemporaryFile(
            "w", dir=self.io_root, delete=False, encoding="utf-8"
        ) as payload:
            payload.write(content)
            return Path(payload.name)


def _http_argv(url: str) -> list[str]:
    try:
        parts = urlsplit(url)
        host = parts.hostname
        if url.startswith("-") or parts.scheme not in ("http", "https") or not host:
            raise _InvalidArguments("http_get: url must be an http or https URL")
        port = parts.port or (443 if parts.scheme == "https" else 80)
    except _InvalidArguments:
        raise
    except (ValueError, UnicodeError) as exc:
        raise _InvalidArguments(f"http_get: invalid url: {exc}") from None
    argv = [str(CURL), "-sS", "--max-time", "10", "--url", url]
    address = _resolve(host, port)
    if address is not None:
        argv += ["--resolve", f"{host}:{port}:{address}"]
    return argv


def _resolve(host: str, port: int) -> str | None:
    """Resolve in the parent: the jail allows TCP only, not DNS. IP literals need no lookup.

    shortcut: getaddrinfo has no timeout; a hung resolver delays the action past the wall budget.
    """
    try:
        ipaddress.ip_address(host)
        return None
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except (OSError, UnicodeError) as exc:
        raise _InvalidArguments(f"http_get: cannot resolve {host!r}: {exc}") from None
    return str(infos[0][4][0])


def _string_arg(call: ToolCall, name: str) -> str:
    value = call.arguments.get(name)
    if not isinstance(value, str) or not value:
        raise _InvalidArguments(f"{call.name}: {name} must be a non-empty string")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        raise _InvalidArguments(f"{call.name}: {name} is not valid unicode") from None
    if "\x00" in value:
        raise _InvalidArguments(f"{call.name}: {name} must not contain a NUL byte")
    return value


def _capped(text: str) -> str:
    data = text.encode("utf-8")
    if len(data) <= MAX_TOOL_PAYLOAD_BYTES:
        return text
    return data[:MAX_TOOL_PAYLOAD_BYTES].decode("utf-8", "ignore")
