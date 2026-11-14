import http.server
import os
import shutil
import sys
import threading
from pathlib import Path

import pytest

from assay.agent import ToolCall
from assay.agent.tools import Toolbox
from assay.mcp.client import MCPClient, PROTOCOL_VERSION
from assay.sandbox import DenialClass, JailConfig, Limits, NetRule
from assay.sandbox.bubblewrap import BubblewrapSandbox

pytestmark = pytest.mark.skipif(
    sys.platform != "linux" or shutil.which("bwrap") is None,
    reason="bubblewrap is Linux-only",
)

FIXTURE = Path(__file__).parent / "fixtures" / "mcp_server.py"


@pytest.fixture
def sandbox():
    exe = shutil.which("bwrap")
    if exe is None:
        pytest.skip("bwrap is not installed")
    return BubblewrapSandbox(Path(exe))


def config_for(tmp_path, *, keep=False, **over):
    root = tmp_path / "run"
    root.mkdir(exist_ok=True)
    return JailConfig(
        run_root=root,
        limits=Limits(wall_seconds=10.0),
        keep=keep,
        **over,
    )


def test_write_inside_and_outside(tmp_path, sandbox):
    config = config_for(tmp_path, keep=True)
    host_escape = Path("/var/tmp") / f"assay-escape-{os.getpid()}"
    host_escape.unlink(missing_ok=True)

    record = sandbox.run(
        ["/bin/sh", "-c", f"echo inside > ok; echo outside > {host_escape}"],
        config,
    )

    assert record.exit_code != 0
    assert (config.run_root / "ok").read_text() == "inside\n"
    assert not host_escape.exists()
    shutil.rmtree(config.run_root, ignore_errors=True)


def test_home_and_etc_are_hidden(tmp_path, sandbox):
    config = config_for(tmp_path)

    record = sandbox.run(
        [
            "/bin/sh",
            "-c",
            "test ! -e /home && test ! -e /root && test ! -e /etc/hostname",
        ],
        config,
    )

    assert record.exit_code == 0, record.stderr


def test_env_is_scrubbed(tmp_path, sandbox, monkeypatch):
    monkeypatch.setenv("ASSAY_TEST_SECRET", "s3cr3t")
    config = config_for(tmp_path, env={"ASSAY_ALLOWED": "yes"})

    record = sandbox.run(
        ["/bin/sh", "-c", 'printf "%s\\n" "$ASSAY_TEST_SECRET" "$ASSAY_ALLOWED"'],
        config,
    )

    assert record.exit_code == 0
    assert record.stdout == "\nyes\n"


def test_network_is_denied(tmp_path, sandbox):
    bash = "/bin/bash" if Path("/bin/bash").exists() else shutil.which("bash")
    if bash is None:
        pytest.skip("bash is not installed")
    config = config_for(tmp_path)

    record = sandbox.run([bash, "-c", "exec 3<>/dev/tcp/1.1.1.1/80"], config)

    assert record.exit_code != 0


def test_wall_limit_is_recorded(tmp_path, sandbox):
    config = config_for(tmp_path)
    config = JailConfig(
        run_root=config.run_root,
        limits=Limits(wall_seconds=0.5),
    )

    record = sandbox.run(["/bin/sh", "-c", "sleep 5"], config)

    assert record.limit_exceeded == "wall_seconds"
    assert record.exit_code != 0


def test_keep_preserves_and_default_removes(tmp_path, sandbox):
    kept = config_for(tmp_path, keep=True)
    sandbox.run(["/bin/true"], kept)
    assert kept.run_root.exists()
    shutil.rmtree(kept.run_root, ignore_errors=True)

    removed = config_for(tmp_path)
    sandbox.run(["/bin/true"], removed)
    assert not removed.run_root.exists()


def test_capture_directory_is_read_only(tmp_path, sandbox):
    config = config_for(tmp_path, keep=True)
    capture = config.run_root / ".assay"
    capture.mkdir(exist_ok=True)
    marker = capture / "marker"
    marker.write_text("original")

    record = sandbox.run(["/bin/sh", "-c", "echo forged > .assay/marker"], config)

    assert record.exit_code != 0
    assert marker.read_text() == "original"
    shutil.rmtree(config.run_root, ignore_errors=True)


def test_symlink_escape_is_denied(tmp_path, sandbox):
    config = config_for(tmp_path, keep=True)
    (config.run_root / "link").symlink_to("/etc/hostname")

    record = sandbox.run(["/bin/cat", "link"], config)

    assert record.exit_code != 0
    shutil.rmtree(config.run_root, ignore_errors=True)


def test_toolbox_write_and_read(tmp_path, sandbox):
    run_root = tmp_path / "run"
    run_root.mkdir()

    with Toolbox(sandbox, run_root) as box:
        written = box.execute(
            ToolCall(
                id="write",
                name="write_file",
                arguments={"path": "hello.txt", "content": "hello from linux"},
            )
        )
        assert written.ok, written.output

        read = box.execute(
            ToolCall(id="read", name="read_file", arguments={"path": "hello.txt"})
        )
        assert read.ok, read.output
        assert read.output == "hello from linux"


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def _serve():
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _QuietHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def _network_supported() -> bool:
    if not Path("/usr/bin/python3").exists():
        return False
    try:
        major, minor = (int(part) for part in os.uname().release.split(".")[:2])
    except (AttributeError, ValueError):
        return False
    if (major, minor) < (6, 7):
        return False
    return any(
        Path(path).exists()
        for path in (
            "/lib/x86_64-linux-gnu/libseccomp.so.2",
            "/usr/lib/x86_64-linux-gnu/libseccomp.so.2",
            "/lib/aarch64-linux-gnu/libseccomp.so.2",
            "/usr/lib/aarch64-linux-gnu/libseccomp.so.2",
            "/lib64/libseccomp.so.2",
            "/usr/lib64/libseccomp.so.2",
        )
    )


requires_network = pytest.mark.skipif(
    not _network_supported(), reason="Landlock ABI 4 + libseccomp are required"
)


@requires_network
def test_network_port_allowlist(tmp_path, sandbox):
    curl = "/usr/bin/curl" if Path("/usr/bin/curl").exists() else shutil.which("curl")
    if curl is None:
        pytest.skip("curl is not installed")
    allowed = _serve()
    denied = _serve()
    try:
        allowed_port = allowed.server_address[1]
        denied_port = denied.server_address[1]

        config = config_for(
            tmp_path, allow_network=(NetRule("*", allowed_port),)
        )
        ok = sandbox.run(
            [
                curl,
                "-sS",
                "--max-time",
                "2",
                f"http://127.0.0.1:{allowed_port}/",
            ],
            config,
        )
        assert ok.exit_code == 0, ok.stderr

        config = config_for(
            tmp_path, allow_network=(NetRule("*", allowed_port),)
        )
        blocked = sandbox.run(
            [
                curl,
                "-sS",
                "--max-time",
                "2",
                f"http://127.0.0.1:{denied_port}/",
            ],
            config,
        )
        assert blocked.exit_code != 0
    finally:
        allowed.shutdown()
        denied.shutdown()


@requires_network
def test_network_udp_is_denied(tmp_path, sandbox):
    config = config_for(tmp_path, allow_network=(NetRule("*", 443),))
    record = sandbox.run(
        [
            "/usr/bin/python3",
            "-c",
            "import socket; socket.socket(socket.AF_INET, socket.SOCK_DGRAM)",
        ],
        config,
    )

    assert record.exit_code != 0


def test_mcp_fixture_starts_under_bwrap(tmp_path, sandbox):
    python = "/usr/bin/python3"
    if not Path(python).exists():
        pytest.skip("/usr/bin/python3 is not installed")
    run_root = tmp_path / "run"
    run_root.mkdir()
    shutil.copy2(FIXTURE, run_root / "mcp_server.py")
    (run_root / "inside.txt").write_text("inside\n")
    config = JailConfig(
        run_root=run_root,
        limits=Limits(wall_seconds=30.0, cpu_seconds=30),
    )

    with sandbox.start_session(
        [python, "-u", str(run_root / "mcp_server.py")], config
    ) as session:
        client = MCPClient(session, timeout=5.0)
        init = client.initialize()
        assert init["protocolVersion"] == PROTOCOL_VERSION
        assert {tool.name for tool in client.list_tools()} == {
            "echo",
            "read_inside",
            "read_outside",
            "slow",
        }
        echo = client.call_tool("echo", {"text": "hello"})
        assert echo.ok and echo.text == "hello"
        inside = client.call_tool("read_inside", {"path": "inside.txt"})
        assert inside.ok and inside.text == "inside\n"
        outside = client.call_tool("read_outside", {"path": "/etc/hostname"})
        assert not outside.ok
        client.close()

    record = session.record
    assert record is not None
    assert record.exit_code == 0
    assert record.timed_out is False
    assert any(denial.kind is DenialClass.FILE_READ for denial in record.denials)
