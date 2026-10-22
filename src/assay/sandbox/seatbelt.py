"""macOS Seatbelt backend: build the profile, then launch the child inside it."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from .config import JailConfig
from .records import RunRecord

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
    ]
    lines.extend(
        f'(allow network-outbound (remote tcp "{rule.host}:{rule.port}"))'
        for rule in config.allow_network
    )
    return "\n".join(lines) + "\n"


class SeatbeltSandbox:
    def __init__(self, sandbox_exec: Path) -> None:
        self.sandbox_exec = Path(sandbox_exec)

    def run(self, argv: Sequence[str], config: JailConfig) -> RunRecord:
        raise NotImplementedError
