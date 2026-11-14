import os
import shutil
import sys
import time
from pathlib import Path

import pytest

from assay.capture import EventKind, EventOutcome
from assay.mcp.client import MCPClient, MCPTimeout, PROTOCOL_VERSION
from assay.mcp.events import event_for_call
from assay.sandbox import JailConfig, Limits
from assay.sandbox.records import DenialClass
from assay.sandbox.seatbelt import SeatbeltSandbox

pytestmark = pytest.mark.skipif(
    sys.platform != "darwin" or shutil.which("sandbox-exec") is None,
    reason="Seatbelt is macOS-only",
)

FIXTURE = Path(__file__).parent / "fixtures" / "mcp_server.py"
PY = "/usr/bin/python3"
SANDBOX = "/usr/bin/sandbox-exec"


def make_config(tmp_path, *, keep=False):
    root = tmp_path / "run"
    root.mkdir()
    shutil.copy2(FIXTURE, root / "mcp_server.py")
    (root / "inside.txt").write_text("inside\n")
    return JailConfig(
        run_root=root,
        limits=Limits(wall_seconds=30.0, cpu_seconds=30),
        keep=keep,
    )


def start(config):
    return SeatbeltSandbox(Path(SANDBOX)).start_session(
        [PY, "-u", str(config.run_root / "mcp_server.py")], config
    )


def test_stdio_server_runs_inside_the_jail(tmp_path):
    config = make_config(tmp_path)

    with start(config) as session:
        client = MCPClient(session, timeout=5.0)
        init = client.initialize()
        assert init["protocolVersion"] == PROTOCOL_VERSION

        tools = client.list_tools()
        assert {tool.name for tool in tools} == {
            "echo",
            "read_inside",
            "read_outside",
            "slow",
        }

        echo = client.call_tool("echo", {"text": "hello"})
        assert echo.ok
        assert echo.text == "hello"

        inside = client.call_tool("read_inside", {"path": "inside.txt"})
        assert inside.ok
        assert inside.text == "inside\n"

        outside = client.call_tool("read_outside", {})
        assert not outside.ok
        assert "denied" in outside.text.lower()

        client.close()

    record = session.record
    assert record is not None
    assert record.exit_code == 0
    assert record.timed_out is False
    assert record.backend == "seatbelt"
    assert record.network_mode == "none"
    assert "assay-denial: file-read" in record.stderr
    assert any(denial.kind is DenialClass.FILE_READ for denial in record.denials)
    assert not config.run_root.exists()

    echo_event = event_for_call("echo", {"text": "hello"}, echo)
    assert echo_event.kind is EventKind.TOOL
    assert echo_event.outcome is EventOutcome.OK

    denials = tuple(f"{denial.kind.value} {denial.detail}" for denial in record.denials)
    outside_event = event_for_call("read_outside", {}, outside, denials=denials)
    assert outside_event.kind is EventKind.TOOL
    assert outside_event.outcome is EventOutcome.DENIED


def test_a_slow_call_times_out_and_tears_down(tmp_path):
    config = make_config(tmp_path)
    session = start(config)
    session.__enter__()
    pid = session.pid
    client = MCPClient(session, timeout=5.0)
    client.initialize()

    with pytest.raises(MCPTimeout):
        client.call_tool("slow", {"seconds": 5}, timeout=0.2)

    record = session.close()
    assert record.timed_out is True

    for _ in range(60):
        try:
            os.kill(pid, 0)
        except (ProcessLookupError, PermissionError):
            return
        time.sleep(0.05)
    pytest.fail(f"orphan {pid} survived teardown")
