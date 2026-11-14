"""Linux bubblewrap backend: namespaces and a minimal root, no daemon and no network."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Sequence

from .config import JailConfig
from .process import run_process
from .records import RunRecord, SandboxUnavailable

if TYPE_CHECKING:
    from .session import SandboxSession

DEFAULT_BWRAP = Path("/usr/bin/bwrap")
DEFAULT_PATH = "/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

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
    if config.allow_network:
        raise SandboxUnavailable(
            "the Linux backend does not support network allowlists yet; "
            "run on macOS for a skill that needs http_get"
        )
    root = str(config.run_root)
    command = [
        str(bwrap),
        "--die-with-parent",
        "--new-session",
        "--unshare-user",
        "--unshare-pid",
        "--unshare-ipc",
        "--unshare-uts",
        "--unshare-net",
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
    command += ["--", *(str(a) for a in argv)]
    return command


def _setup_error(returncode: int, stderr: str) -> str | None:
    if stderr.startswith("bwrap:"):
        return (
            f"bwrap could not establish the jail (exit {returncode}): "
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

        return SandboxSession(
            build_command(self.bwrap, argv, config),
            config,
            path=self.child_path,
            setup_error_prefix="bwrap:",
        )
