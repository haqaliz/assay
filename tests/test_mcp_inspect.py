import json
import shutil
import sys
from collections import deque
from pathlib import Path

import pytest

from assay.mcp.inspect import ServerReport, inspect_server
from assay.mcp.server import Server
from assay.sandbox.records import SandboxFailed
from assay.sandbox.seatbelt import SeatbeltSandbox
from assay.sandbox.session import SessionRecord

requires_seatbelt = pytest.mark.skipif(
    sys.platform != "darwin" or shutil.which("sandbox-exec") is None,
    reason="Seatbelt is macOS-only",
)

FIXTURE = Path(__file__).parent / "fixtures" / "mcp_server.py"
RECORD = SessionRecord(
    exit_code=0,
    signal=None,
    stderr="",
    truncated=False,
    denials=(),
    config_hash="sha256:" + "a" * 64,
    run_root="/tmp/run",
    timed_out=False,
)


def server(**over):
    values = {
        "name": "demo",
        "command": "python3",
        "args": ("-u", "server.py"),
        "source_path": Path("mcp.json"),
        "source_hash": "b" * 64,
    }
    values.update(over)
    return Server(**values)


def reply(request_id, result):
    return json.dumps({"jsonrpc": "2.0", "id": request_id, "result": result})


def initialized(request_id):
    return reply(
        request_id,
        {
            "protocolVersion": "2026-07-28",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "fixture", "version": "1"},
        },
    )


class FakeSession:
    def __init__(self, *lines, fail=None):
        self.lines = deque(lines)
        self.fail = fail
        self.record = None
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def write_line(self, line):
        json.loads(line)

    def read_line(self, deadline):
        if self.fail is not None:
            raise self.fail
        if not self.lines:
            raise TimeoutError("no line")
        return self.lines.popleft()

    def close(self):
        self.closed = True
        if self.record is None:
            self.record = RECORD


class FakeSandbox:
    child_path = "/usr/bin:/bin"

    def __init__(self, session=None, error=None):
        self.session = session
        self.error = error

    def start_session(self, argv, config):
        if self.error is not None:
            raise self.error
        return self.session


def test_a_successful_inspection_reports_the_tools(tmp_path):
    session = FakeSession(
        initialized(1),
        reply(2, {"tools": [{"name": "echo", "description": "Echo"}]}),
    )
    run_root = tmp_path / "run"
    run_root.mkdir()

    report = inspect_server(
        server(), run_root=run_root, sandbox=FakeSandbox(session)
    )

    assert isinstance(report, ServerReport)
    assert report.started is True
    assert report.protocol_version == "2026-07-28"
    assert [tool.name for tool in report.tools] == ["echo"]
    assert report.session is RECORD
    assert report.error is None
    assert session.closed is True


def test_a_startup_failure_becomes_a_report_error(tmp_path):
    run_root = tmp_path / "run"
    run_root.mkdir()

    report = inspect_server(
        server(),
        run_root=run_root,
        sandbox=FakeSandbox(error=SandboxFailed("could not start sandbox-exec: nope")),
    )

    assert report.started is False
    assert report.session is None
    assert "SandboxFailed" in report.error
    assert "nope" in report.error


def test_a_timeout_becomes_a_report_error(tmp_path):
    session = FakeSession(fail=TimeoutError("no line"))
    run_root = tmp_path / "run"
    run_root.mkdir()

    report = inspect_server(
        server(), run_root=run_root, sandbox=FakeSandbox(session)
    )

    assert report.started is False
    assert report.session is RECORD
    assert "MCPTimeout" in report.error
    assert session.closed is True


def test_a_tools_list_failure_keeps_the_handshake_result(tmp_path):
    session = FakeSession(initialized(1), "not json")
    run_root = tmp_path / "run"
    run_root.mkdir()

    report = inspect_server(
        server(), run_root=run_root, sandbox=FakeSandbox(session)
    )

    assert report.started is True
    assert report.protocol_version == "2026-07-28"
    assert report.tools == ()
    assert "MCPProtocolError" in report.error
    assert report.session is RECORD


@requires_seatbelt
def test_the_fixture_server_starts_in_the_jail(tmp_path):
    fixture = tmp_path / "mcp_server.py"
    shutil.copy2(FIXTURE, fixture)
    run_root = tmp_path / "run"
    run_root.mkdir()
    real = server(command="/usr/bin/python3", args=("-u", str(fixture)))

    report = inspect_server(
        real,
        run_root=run_root,
        sandbox=SeatbeltSandbox(Path("/usr/bin/sandbox-exec")),
        timeout=5.0,
    )

    assert report.started is True
    assert report.protocol_version == "2026-07-28"
    assert {tool.name for tool in report.tools} == {
        "echo",
        "read_inside",
        "read_outside",
        "slow",
    }
    assert report.session is not None
    assert report.session.exit_code == 0
    assert report.error is None


@requires_seatbelt
def test_a_missing_command_is_reported_not_raised(tmp_path):
    run_root = tmp_path / "run"
    run_root.mkdir()
    real = server(command="/no/such/mcp-command", args=())

    report = inspect_server(
        real,
        run_root=run_root,
        sandbox=SeatbeltSandbox(Path("/usr/bin/sandbox-exec")),
        timeout=2.0,
    )

    assert report.started is False
    assert report.error is not None
    assert "SandboxFailed" in report.error
