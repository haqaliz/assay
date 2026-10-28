"""Real Seatbelt confinement through the Toolbox; macOS only.

These spawn a real jail but touch only tmp_path and the local host filesystem.
"""

import shutil
import sys
from pathlib import Path

import pytest

from assay.agent import ToolCall, Toolbox
from assay.sandbox.seatbelt import SeatbeltSandbox

pytestmark = pytest.mark.skipif(
    sys.platform != "darwin" or shutil.which("sandbox-exec") is None,
    reason="Seatbelt is macOS-only",
)


def call(name, **arguments):
    return ToolCall(id="t1", name=name, arguments=arguments)


@pytest.fixture
def toolbox(tmp_path):
    root = tmp_path / "run"
    root.mkdir()
    return Toolbox(SeatbeltSandbox(Path("/usr/bin/sandbox-exec")), root)


def test_write_inside_the_run_root_succeeds(toolbox):
    result = toolbox.execute(call("write_file", path="inside.md", content="hello\n"))
    assert result.ok, result.output
    assert (toolbox.run_root / "inside.md").read_text() == "hello\n"


def test_write_outside_the_run_root_is_denied_and_captured(toolbox):
    escape = toolbox.run_root.parent / "escape.md"
    result = toolbox.execute(call("write_file", path="../escape.md", content="nope"))
    assert not result.ok
    assert result.record is not None
    # shortcut: BSD cp only says "Operation not permitted", which A2 records as UNKNOWN; A4
    # classifies by the tool call. Assert the denial is captured, not its heuristic kind.
    assert any("../escape.md" in denial.detail for denial in result.record.denials)
    assert not escape.exists()


def test_read_of_host_ssh_is_not_ok(toolbox):
    result = toolbox.execute(call("read_file", path=str(Path.home() / ".ssh")))
    assert not result.ok
    assert result.record is not None
