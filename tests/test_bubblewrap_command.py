from pathlib import Path

import pytest

from assay.sandbox import JailConfig, NetRule
from assay.sandbox.bubblewrap import NET_PYTHON, BubblewrapSandbox, build_command
from assay.sandbox.records import SandboxFailed, SandboxUnavailable


def config_for(tmp_path, **over):
    root = tmp_path / "run"
    root.mkdir(exist_ok=True)
    return JailConfig(run_root=root, **over)


def test_command_uses_namespaces_and_no_network(tmp_path):
    config = config_for(tmp_path)
    command = build_command(Path("/usr/bin/bwrap"), ["/bin/true"], config)

    assert command[0] == "/usr/bin/bwrap"
    assert "--unshare-net" in command
    assert "--unshare-user" in command
    assert "--die-with-parent" in command
    assert "--cap-drop" in command
    assert "--share-net" not in command


def test_command_binds_run_root_and_protects_capture(tmp_path):
    config = config_for(tmp_path)
    root = str(config.run_root)
    command = build_command(Path("/usr/bin/bwrap"), ["/bin/true"], config)

    assert command[command.index("--bind") + 1 : command.index("--bind") + 3] == [root, root]
    assert f"{root}/.assay" in command
    assert "--ro-bind-try" in command


def test_command_binds_extra_reads_and_env(tmp_path):
    extra = tmp_path / "extra"
    extra.mkdir()
    config = config_for(
        tmp_path,
        allow_read_extra=(extra,),
        env={"ASSAY_TEST": "yes"},
    )
    command = build_command(Path("/usr/bin/bwrap"), ["/bin/true"], config)

    assert "--clearenv" in command
    assert command[command.index("--setenv") + 1 : command.index("--setenv") + 3] == [
        "PATH",
        "/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
    ]
    assert "ASSAY_TEST" in command
    assert "yes" in command
    assert str(extra) in command


def test_network_allowlist_uses_share_net_and_launcher(tmp_path):
    config = config_for(tmp_path, allow_network=(NetRule("*", 443),))
    command = build_command(Path("/usr/bin/bwrap"), ["/bin/true"], config)

    assert "--share-net" in command
    assert "--unshare-net" not in command
    assert str(NET_PYTHON) in command
    assert any("PORTS = (443,)" in part for part in command)


def test_localhost_network_is_refused(tmp_path):
    config = config_for(tmp_path, allow_network=(NetRule("localhost", 443),))

    with pytest.raises(SandboxUnavailable, match="localhost"):
        build_command(Path("/usr/bin/bwrap"), ["/bin/true"], config)


def test_bwrap_setup_error_is_sandbox_failed(tmp_path):
    bwrap = tmp_path / "bwrap"
    bwrap.write_text("#!/bin/sh\necho 'bwrap: no namespaces' >&2\nexit 1\n")
    bwrap.chmod(0o755)
    config = config_for(tmp_path)

    with pytest.raises(SandboxFailed, match="bwrap"):
        BubblewrapSandbox(bwrap).run(["/bin/true"], config)
