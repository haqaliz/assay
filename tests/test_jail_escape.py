"""M0.2 acceptance: the jail actually confines, on this machine.

Real-confinement tests. They bind loopback only; no external host is contacted.
Skipped off macOS because there is no backend yet (fail-closed by design).
"""

import json
import os
import socket
import sys
from pathlib import Path

import pytest

from assay.sandbox import DenialClass, JailConfig, Limits, NetRule
from assay.sandbox.seatbelt import SeatbeltSandbox

pytestmark = pytest.mark.skipif(sys.platform != "darwin", reason="Seatbelt is macOS-only")

PY = "/usr/bin/python3"
FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def sandbox():
    return SeatbeltSandbox(Path("/usr/bin/sandbox-exec"))


def make_config(tmp_path, **over):
    root = tmp_path / "run"
    root.mkdir(parents=True, exist_ok=True)
    over.setdefault("limits", Limits(wall_seconds=20.0))
    return JailConfig(run_root=root, **over)


def results(record):
    for line in record.stdout.splitlines():
        if line.startswith("RESULT "):
            return json.loads(line[len("RESULT ") :])
    raise AssertionError(f"probe produced no result; stdout={record.stdout!r} stderr={record.stderr!r}")


def stage(config, name):
    """Inputs must live inside the run root: the jail denies /Users, by design."""
    source = FIXTURES / name
    target = config.run_root / name
    target.write_bytes(source.read_bytes())
    return target


def run_fs(sandbox, config, spec):
    probe = stage(config, "probe_fs.py")
    return sandbox.run([PY, str(probe), json.dumps(spec)], config)


class TwoListeners:
    """Two loopback listeners on random ports: one will be allowlisted, one must not be."""

    def __enter__(self):
        self.sockets = []
        for _ in range(2):
            sock = socket.socket()
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("127.0.0.1", 0))
            sock.listen(4)
            self.sockets.append(sock)
        return tuple(sock.getsockname()[1] for sock in self.sockets)

    def __exit__(self, *exc):
        for sock in self.sockets:
            sock.close()
        return False


def test_writes_are_confined(sandbox, tmp_path):
    config = make_config(tmp_path)
    outside = tmp_path / "outside.txt"
    record = run_fs(
        sandbox,
        config,
        [
            {"name": "inside", "path": str(config.run_root / "inside.txt"), "mode": "write"},
            {"name": "outside", "path": str(outside), "mode": "write"},
        ],
    )
    assert results(record) == {"inside": "ALLOWED", "outside": "DENIED"}
    assert not outside.exists()
    assert any(denial.kind is DenialClass.FILE_WRITE for denial in record.denials)


def test_host_data_is_unreadable(sandbox, tmp_path):
    config = make_config(tmp_path)
    config.run_root.joinpath("link").symlink_to("/etc/passwd")
    traversal = os.path.join(str(config.run_root), os.path.relpath("/etc/passwd", config.run_root))
    record = run_fs(
        sandbox,
        config,
        [
            {"name": "etc", "path": "/etc/passwd", "mode": "read"},
            {"name": "home", "path": os.path.expanduser("~/.zshrc"), "mode": "read"},
            {"name": "ssh_dir", "path": os.path.expanduser("~/.ssh"), "mode": "list"},
            {"name": "traversal", "path": traversal, "mode": "read"},
            {"name": "symlink", "path": str(config.run_root / "link"), "mode": "read"},
            {"name": "etc_write", "path": "/private/etc/assay-escape.txt", "mode": "write"},
        ],
    )
    assert results(record) == {
        "etc": "DENIED",
        "home": "DENIED",
        "ssh_dir": "DENIED",
        "traversal": "DENIED",
        "symlink": "DENIED",
        "etc_write": "DENIED",
    }
    assert not Path("/private/etc/assay-escape.txt").exists()
    assert len([d for d in record.denials if d.kind is DenialClass.FILE_READ]) >= 5


def test_network_is_denied_by_default(sandbox, tmp_path):
    config = make_config(tmp_path)
    probe = stage(config, "probe_net.py")
    with TwoListeners() as (first, second):
        record = sandbox.run([PY, str(probe), str(first), str(second)], config)
    assert "CONNECTED" not in record.stdout
    assert record.stdout.count("DENIED") >= 2
    assert any(denial.kind is DenialClass.NETWORK for denial in record.denials)


def test_allowlist_is_port_scoped(sandbox, tmp_path):
    with TwoListeners() as (allowed, denied):
        config = make_config(tmp_path, allow_network=(NetRule("localhost", allowed),))
        probe = stage(config, "probe_net.py")
        record = sandbox.run([PY, str(probe), str(allowed), str(denied)], config)
    assert "ALLOWED_PORT: CONNECTED" in record.stdout
    assert "DENIED_PORT: DENIED" in record.stdout
    assert any(denial.kind is DenialClass.NETWORK for denial in record.denials)
    assert record.ok
