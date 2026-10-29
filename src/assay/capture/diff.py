"""Diff observed events against declared scope. No verdicts live here; A5 owns those."""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from enum import StrEnum

from assay.ingest import Skill

from .capture import _host_port
from .records import Event, EventKind, Trace


class Dimension(StrEnum):
    FILES = "files"
    NETWORK = "network"
    SHELL = "shell"
    INSTRUCTIONS = "instructions"


class DimensionStatus(StrEnum):
    DECLARED = "declared"
    UNDECLARED = "undeclared"


class DivergenceStatus(StrEnum):
    EXCEEDED = "exceeded"
    UNDECLARED = "undeclared"


@dataclass(frozen=True, slots=True)
class Divergence:
    kind: EventKind
    target: str
    status: DivergenceStatus
    reason: str


@dataclass(frozen=True, slots=True)
class Coverage:
    dimension: Dimension
    declared: bool
    events: int


@dataclass(frozen=True, slots=True)
class Diff:
    divergences: tuple[Divergence, ...]
    coverage: tuple[Coverage, ...]


def diff(skill: Skill, trace: Trace) -> Diff:
    scope = skill.scope
    counts = {dimension: 0 for dimension in Dimension}
    divergences: list[Divergence] = []
    for event in trace.events:
        divergence: Divergence | None = None
        if event.kind in (EventKind.FILE_READ, EventKind.FILE_WRITE):
            counts[Dimension.FILES] += 1
            divergence = _file_divergence(event, scope.files)
        elif event.kind is EventKind.NETWORK:
            counts[Dimension.NETWORK] += 1
            divergence = _network_divergence(event, scope.network)
        elif event.kind is EventKind.SHELL:
            counts[Dimension.SHELL] += 1
            divergence = _shell_divergence(event, scope.tools)
        elif event.kind is EventKind.INSTRUCTION:
            counts[Dimension.INSTRUCTIONS] += 1
        if divergence is not None:
            divergences.append(divergence)
    return Diff(
        divergences=tuple(divergences),
        coverage=(
            Coverage(Dimension.FILES, scope.files is not None, counts[Dimension.FILES]),
            Coverage(Dimension.NETWORK, scope.network is not None, counts[Dimension.NETWORK]),
            Coverage(Dimension.SHELL, scope.tools is not None, counts[Dimension.SHELL]),
            Coverage(Dimension.INSTRUCTIONS, True, counts[Dimension.INSTRUCTIONS]),
        ),
    )


def _file_divergence(event: Event, declared: tuple[str, ...] | None) -> Divergence | None:
    if declared is None:
        return Divergence(
            event.kind, event.target, DivergenceStatus.UNDECLARED, "no file scope declared"
        )
    if not declared:
        return Divergence(
            event.kind, event.target, DivergenceStatus.EXCEEDED, "file scope is declared empty"
        )
    # shortcut: fnmatch * crosses /, so out/* matches out/a/b; revisit if over-permission hides findings.
    if any(
        fnmatch.fnmatchcase(_normalise(event.target), _normalise(pattern))
        for pattern in declared
    ):
        return None
    return Divergence(
        event.kind,
        event.target,
        DivergenceStatus.EXCEEDED,
        f"no declared file pattern matches {event.target!r}",
    )


def _network_divergence(event: Event, declared: tuple[str, ...] | None) -> Divergence | None:
    if declared is None:
        return Divergence(
            event.kind, event.target, DivergenceStatus.UNDECLARED, "no network scope declared"
        )
    if not declared:
        return Divergence(
            event.kind, event.target, DivergenceStatus.EXCEEDED, "network scope is declared empty"
        )
    if any(_host_port(entry) == event.target.lower() for entry in declared):
        return None
    return Divergence(
        event.kind,
        event.target,
        DivergenceStatus.EXCEEDED,
        f"no declared network entry matches {event.target!r}",
    )


def _shell_divergence(
    event: Event, tools: frozenset[str] | None
) -> Divergence | None:
    if tools is None:
        return Divergence(
            event.kind, event.target, DivergenceStatus.UNDECLARED, "no tool scope declared"
        )
    if any(tool == "Bash" or tool.startswith("Bash(") for tool in tools):
        return None
    return Divergence(
        event.kind,
        event.target,
        DivergenceStatus.EXCEEDED,
        "tool scope does not declare Bash",
    )


def _normalise(path: str) -> str:
    return path.removeprefix("./")
