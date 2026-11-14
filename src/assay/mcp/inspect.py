"""Start a stdio MCP server in the jail and report what it exposes. No verdict."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from assay.sandbox import JailConfig, Limits
from assay.sandbox.base import Sandbox
from assay.sandbox.records import SandboxFailed
from assay.sandbox.session import SandboxSession, SessionError, SessionRecord

from .client import MCPClient, MCPError, MCPTool
from .server import Server

SessionFactory = Callable[..., SandboxSession]


@dataclass(frozen=True, slots=True)
class ServerReport:
    server: Server
    started: bool
    protocol_version: str | None
    tools: tuple[MCPTool, ...]
    session: SessionRecord | None
    error: str | None

    def to_payload(self) -> dict[str, object]:
        session = None
        if self.session is not None:
            session = {
                "exit_code": self.session.exit_code,
                "signal": self.session.signal,
                "timed_out": self.session.timed_out,
                "config_hash": self.session.config_hash,
                "backend": self.session.backend,
                "network_mode": self.session.network_mode,
                "run_root": self.session.run_root,
                "teardown_error": self.session.teardown_error,
                "denials": [
                    {"kind": denial.kind.value, "detail": denial.detail}
                    for denial in self.session.denials
                ],
            }
        return {
            "server": {
                "name": self.server.name,
                "command": self.server.command,
                "args": list(self.server.args),
                "transport": self.server.transport,
                "source_path": str(self.server.source_path),
                "source_hash": self.server.source_hash,
            },
            "started": self.started,
            "protocol_version": self.protocol_version,
            "tools": [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": dict(tool.input_schema),
                }
                for tool in self.tools
            ],
            "session": session,
            "error": self.error,
        }


def inspect_server(
    server: Server,
    *,
    run_root: Path,
    sandbox: Sandbox,
    timeout: float = 10.0,
    keep: bool = False,
    session_factory: SessionFactory | None = None,
) -> ServerReport:
    config = JailConfig(
        run_root=run_root,
        limits=Limits(wall_seconds=30.0, cpu_seconds=30),
        keep=keep,
    )
    argv = [server.command, *server.args]
    session: SandboxSession | None = None
    record: SessionRecord | None = None
    started = False
    protocol: str | None = None
    tools: tuple[MCPTool, ...] = ()
    error: str | None = None

    try:
        if session_factory is None:
            session = sandbox.start_session(argv, config)
        else:
            session = session_factory(argv, config, path=sandbox.child_path)
        with session:
            client = MCPClient(session, timeout=timeout)
            init = client.initialize()
            started = True
            version = init.get("protocolVersion")
            protocol = version if isinstance(version, str) else None
            tools = client.list_tools()
        record = session.record
    except (SandboxFailed, SessionError, MCPError, OSError) as exc:
        error = f"{type(exc).__name__}: {exc}"
        if session is not None:
            if session.record is None:
                try:
                    session.close()
                except Exception:
                    pass
            record = session.record

    return ServerReport(
        server=server,
        started=started,
        protocol_version=protocol,
        tools=tools,
        session=record,
        error=error,
    )
