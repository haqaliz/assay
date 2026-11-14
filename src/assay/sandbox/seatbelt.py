"""macOS Seatbelt backend: build the profile, then launch the child inside it."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Sequence

from .config import DEFAULT_PATH, JailConfig
from .process import run_process
from .records import RunRecord

if TYPE_CHECKING:
    from .session import SandboxSession

# Host data that must never be readable from inside the jail, even though reads are otherwise
# broad (a narrow allow-list kills the child with a silent SIGABRT — see the planning dig note).
HOST_DATA_DENY = ("/Users", "/Volumes", "/private/etc", "/private/var/db")


def build_profile(config: JailConfig) -> str:
    root = str(config.run_root)
    denies = " ".join(f'(subpath "{path}")' for path in HOST_DATA_DENY)
    reads = [f'(subpath "{root}")', *(f'(subpath "{p}")' for p in config.allow_read_extra)]
    lines = [
        "(version 1)",
        "(deny default)",
        "(allow process*)",
        "(allow sysctl-read)",
        "(allow mach-lookup)",
        "(allow signal)",
        "(allow file-read*)",
        f"(deny file-read* {denies})",
        # Re-allowed after the deny: Seatbelt is last-match-wins, and the run root may sit
        # under /Users (e.g. a temp dir inside the checkout).
        f"(allow file-read* {' '.join(reads)})",
        f'(allow file-write* (subpath "{root}") (literal "/dev/null"))',
        # Last match wins: the child may write its run root, never the capture files it is
        # observed through. Without this a shell command can truncate or forge `.assay/*`.
        f'(deny file-write* (subpath "{root}/.assay"))',
    ]
    lines.extend(
        f'(allow network-outbound (remote tcp "{rule.host}:{rule.port}"))'
        for rule in config.allow_network
    )
    return "\n".join(lines) + "\n"


def _setup_error(returncode: int, stderr: str) -> str | None:
    if returncode in (65, 71) or stderr.startswith("sandbox-exec:"):
        return (
            f"sandbox-exec could not establish the jail (exit {returncode}): "
            f"{stderr.strip()[:200]}"
        )
    return None


class SeatbeltSandbox:
    backend = "seatbelt"
    child_path = DEFAULT_PATH

    def __init__(self, sandbox_exec: Path) -> None:
        self.sandbox_exec = Path(sandbox_exec)

    def _command(self, argv: Sequence[str], config: JailConfig) -> list[str]:
        return [
            str(self.sandbox_exec),
            "-p",
            build_profile(config),
            *(str(a) for a in argv),
        ]

    def run(self, argv: Sequence[str], config: JailConfig) -> RunRecord:
        if not argv:
            raise ValueError("argv must not be empty")
        return run_process(
            self._command(argv, config),
            config,
            path=self.child_path,
            start_error="sandbox-exec",
            setup_error=_setup_error,
        )

    def start_session(
        self, argv: Sequence[str], config: JailConfig
    ) -> "SandboxSession":
        from .session import SandboxSession

        return SandboxSession(
            self._command(argv, config),
            config,
            path=self.child_path,
            setup_error_prefix="sandbox-exec:",
        )
