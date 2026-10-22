"""The seam every untrusted run goes through, and the fail-closed backend selection."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Protocol, Sequence

from .config import JailConfig
from .records import RunRecord, SandboxUnavailable

DEFAULT_SANDBOX_EXEC = Path("/usr/bin/sandbox-exec")


class Sandbox(Protocol):
    def run(self, argv: Sequence[str], config: JailConfig) -> RunRecord: ...


def select_sandbox(
    platform: str | None = None, sandbox_exec: Path = DEFAULT_SANDBOX_EXEC
) -> Sandbox:
    """Return a confining backend or raise. There is deliberately no unconfined fallback."""
    plat = platform if platform is not None else sys.platform
    if plat == "darwin":
        if not Path(sandbox_exec).exists():
            raise SandboxUnavailable(
                f"sandbox-exec not found at {sandbox_exec}; refusing to run unconfined"
            )
        from .seatbelt import SeatbeltSandbox

        return SeatbeltSandbox(sandbox_exec=Path(sandbox_exec))
    raise SandboxUnavailable(
        f"no confining sandbox backend for platform {plat!r}; refusing to run unconfined"
    )
