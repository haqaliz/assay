"""Linux bubblewrap backend: namespaces, a minimal root, and an optional TCP port allowlist."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, Sequence

from .config import JailConfig
from .net import launcher_code
from .process import run_process
from .records import RunRecord, SandboxUnavailable

if TYPE_CHECKING:
    from .session import SandboxSession

DEFAULT_BWRAP = Path("/usr/bin/bwrap")
DEFAULT_PATH = "/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
NET_PYTHON = Path("/usr/bin/python3")

# Read-only host trees needed by ordinary runtimes. /home, /root, /var and /opt stay hidden;
# /etc is a private tmpfs with only the selected files below.
_SYSTEM_BINDS = ("/usr", "/bin", "/sbin", "/lib", "/lib64", "/lib32")
_ETC_FILES = (
    "/etc/ssl/certs",
    "/etc/openssl",
    "/etc/hosts",
    "/etc/passwd",
    "/etc/group",
    "/etc/nsswitch.conf",
    "/etc/ld.so.cache",
    "/etc/localtime",
)


def build_command(bwrap: Path, argv: Sequence[str], config: JailConfig) -> list[str]:
    target = [str(a) for a in argv]
    network = ["--unshare-net"]
    if config.allow_network:
        if any(rule.host != "*" for rule in config.allow_network):
            raise SandboxUnavailable(
                "the Linux backend cannot pin network rules to localhost; use host '*'"
            )
        ports = sorted({rule.port for rule in config.allow_network})
        network = ["--share-net"]
        target = [str(NET_PYTHON), "-c", launcher_code(ports), *target]
    root = str(config.run_root)
    command = [
        str(bwrap),
        "--die-with-parent",
        "--new-session",
        "--unshare-user",
        "--unshare-pid",
        "--unshare-ipc",
        "--unshare-uts",
        *network,
        "--cap-drop",
        "ALL",
    ]
    for path in _SYSTEM_BINDS:
        command += ["--ro-bind-try", path, path]
    command += ["--tmpfs", "/etc"]
    for path in _ETC_FILES:
        command += ["--ro-bind-try", path, path]
    command += ["--tmpfs", "/tmp", "--tmpfs", "/run", "--proc", "/proc", "--dev", "/dev"]
    for path in config.allow_read_extra:
        command += ["--ro-bind-try", str(path), str(path)]
    command += [
        "--bind",
        root,
        root,
        # The capture files are opened by the parent before the child starts. A read-only
        # bind stops the child from truncating or forging them by path.
        "--ro-bind-try",
        f"{root}/.assay",
        f"{root}/.assay",
        "--chdir",
        root,
        "--clearenv",
        "--setenv",
        "PATH",
        DEFAULT_PATH,
    ]
    for key, value in config.env.items():
        command += ["--setenv", key, value]
    command += ["--", *target]
    return command


def _setup_error(returncode: int, stderr: str) -> str | None:
    if stderr.startswith("bwrap:"):
        return (
            f"bwrap could not establish the jail (exit {returncode}): "
            f"{stderr.strip()[:200]}"
        )
    if stderr.startswith("assay-launcher:"):
        return (
            f"sandbox network launcher failed (exit {returncode}): "
            f"{stderr.strip()[:200]}"
        )
    return None


class BubblewrapSandbox:
    backend = "bubblewrap"
    child_path = DEFAULT_PATH

    def __init__(self, bwrap: Path = DEFAULT_BWRAP) -> None:
        self.bwrap = Path(bwrap)

    def run(self, argv: Sequence[str], config: JailConfig) -> RunRecord:
        if not argv:
            raise ValueError("argv must not be empty")
        config = replace(config, backend="bubblewrap")
        return run_process(
            build_command(self.bwrap, argv, config),
            config,
            path=self.child_path,
            start_error="bwrap",
            setup_error=_setup_error,
        )

    def start_session(
        self, argv: Sequence[str], config: JailConfig
    ) -> "SandboxSession":
        from .session import SandboxSession

        config = replace(config, backend="bubblewrap")
        return SandboxSession(
            build_command(self.bwrap, argv, config),
            config,
            path=self.child_path,
            setup_error_prefix="bwrap:",
        )
