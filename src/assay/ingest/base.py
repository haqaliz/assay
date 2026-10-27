"""The seam every skill format goes through. Parsing is data extraction, never execution."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from .records import Skill


@runtime_checkable
class Parser(Protocol):
    def parse(self, path: Path) -> Skill: ...
