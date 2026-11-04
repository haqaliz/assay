"""Pre-run requirement policy: what the jail cannot provide."""

from __future__ import annotations

import shutil
import sys
from typing import Callable

from assay.ingest import Skill
from assay.sandbox import DEFAULT_PATH


def _which_on_path(name: str, path: str) -> str | None:
    return shutil.which(name, path=path)


def unmet_requirements(
    skill: Skill,
    *,
    which: Callable[[str, str], str | None] = _which_on_path,
    platform: str = sys.platform,
    path: str = DEFAULT_PATH,
) -> tuple[str, ...]:
    return tuple(
        requirement
        for requirement in skill.requirements
        if not _satisfied(requirement, which=which, platform=platform, path=path)
    )


def _satisfied(
    requirement: str,
    *,
    which: Callable[[str, str], str | None],
    platform: str,
    path: str,
) -> bool:
    prefix, _, value = requirement.partition(":")
    if prefix in ("env", "config"):
        return False
    if prefix == "bin":
        return which(value, path) is not None
    if prefix == "any-bin":
        return any(which(name, path) is not None for name in value.split(","))
    # Ingest validated the prefix; the remaining case is os.
    supported = {"darwin" if name == "macos" else name for name in value.split(",")}
    return platform in supported
