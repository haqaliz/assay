"""Content-addressed trace files. No verdicts live here; A5 owns those."""

from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path

from .records import CaptureError, Trace, TraceIntegrityError


class TraceStore:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        if self.root.is_symlink():
            raise CaptureError(f"trace root must not be a symlink, got {self.root}")
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if not self.root.is_dir():
            raise CaptureError(f"trace root must be a directory, got {self.root}")

    def save(self, trace: Trace) -> Path:
        digest = trace.hash
        path = self.root / f"{digest}.json"
        data = trace.to_json().encode("utf-8")
        fd, tmp_name = tempfile.mkstemp(dir=self.root, prefix=".trace-", suffix=".tmp")
        try:
            with os.fdopen(fd, "wb") as tmp:
                tmp.write(data)
            os.replace(tmp_name, path)
        except BaseException:
            Path(tmp_name).unlink(missing_ok=True)
            raise
        return path

    def load(self, path: Path) -> Trace:
        path = Path(path)
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise CaptureError(f"cannot read trace {path}: {exc}") from None
        digest = hashlib.sha256(data).hexdigest()
        if path.name != f"{digest}.json":
            raise TraceIntegrityError(
                f"{path}: filename does not match content hash {digest}"
            )
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise CaptureError(f"trace {path} is not valid UTF-8: {exc}") from None
        trace = Trace.from_json(text)
        if trace.to_json() != text:
            raise TraceIntegrityError(f"{path}: trace is not in canonical form")
        return trace
