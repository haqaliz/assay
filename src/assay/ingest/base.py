"""The seam every skill format goes through. Parsing is data extraction, never execution."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from .records import Skill


class Parser(Protocol):
    def parse(self, path: Path) -> Skill: ...
