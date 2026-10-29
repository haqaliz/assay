"""Content-addressed trace files. No verdicts live here; A5 owns those."""

from __future__ import annotations

import os
from pathlib import Path

from .records import Trace, TraceIntegrityError


class TraceStore:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, trace: Trace) -> Path:
        digest = trace.hash
        path = self.root / f"{digest}.json"
        tmp = self.root / f".{digest}.tmp"
        tmp.write_text(trace.to_json(), encoding="utf-8")
        os.replace(tmp, path)
        return path

    def load(self, path: Path) -> Trace:
        path = Path(path)
        trace = Trace.from_json(path.read_text(encoding="utf-8"))
        if path.name != f"{trace.hash}.json":
            raise TraceIntegrityError(
                f"{path}: filename does not match content hash {trace.hash}"
            )
        return trace
