"""Diff observed events against declared scope. No verdicts live here; A5 owns those."""

from __future__ import annotations

import fnmatch
import posixpath
from dataclasses import dataclass
from enum import StrEnum

from assay.ingest import Skill

from .capture import _host_port
from .records import CaptureError, Event, EventKind, EventOutcome, Trace


class Dimension(StrEnum):
    FILES = "files"
    NETWORK = "network"
    SHELL = "shell"
    INSTRUCTIONS = "instructions"



class DivergenceStatus(StrEnum):
    EXCEEDED = "exceeded"
    UNDECLARED = "undeclared"


@dataclass(frozen=True, slots=True)
class Divergence:
    kind: EventKind
    target: str
    status: DivergenceStatus
    outcome: EventOutcome
    reason: str
    denials: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Coverage:
    dimension: Dimension
    declared: bool
    events: int


@dataclass(frozen=True, slots=True)
class Diff:
    divergences: tuple[Divergence, ...]
    coverage: tuple[Coverage, ...]
    skill_content_hash: str
    trace_hash: str


def diff(skill: Skill, trace: Trace) -> Diff:
    if trace.skill_content_hash != skill.content_hash:
        raise CaptureError(
            f"trace belongs to skill {trace.skill_content_hash}, not {skill.content_hash}"
        )
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
            # Instructions are not a declared-scope dimension; A5 owns any instruction finding.
            Coverage(Dimension.INSTRUCTIONS, False, counts[Dimension.INSTRUCTIONS]),
        ),
        skill_content_hash=skill.content_hash,
        trace_hash=trace.hash,
    )


def _file_divergence(event: Event, declared: tuple[str, ...] | None) -> Divergence | None:
    if declared is None:
        return Divergence(
            event.kind,
            event.target,
            DivergenceStatus.UNDECLARED,
            event.outcome,
            "no file scope declared",
            event.denials,
        )
    if not declared:
        return Divergence(
            event.kind,
            event.target,
            DivergenceStatus.EXCEEDED,
            event.outcome,
            "file scope is declared empty",
            event.denials,
        )
    # shortcut: fnmatch * crosses /, so out/* matches out/a/b; revisit if over-permission hides findings.
    target = _normalise(event.target)
    if any(fnmatch.fnmatchcase(target, _normalise(pattern)) for pattern in declared):
        return None
    return Divergence(
        event.kind,
        event.target,
        DivergenceStatus.EXCEEDED,
        event.outcome,
        f"no declared file pattern matches {event.target!r}",
        event.denials,
    )


def _network_divergence(event: Event, declared: tuple[str, ...] | None) -> Divergence | None:
    if declared is None:
        return Divergence(
            event.kind,
            event.target,
            DivergenceStatus.UNDECLARED,
            event.outcome,
            "no network scope declared",
            event.denials,
        )
    if not declared:
        return Divergence(
            event.kind,
            event.target,
            DivergenceStatus.EXCEEDED,
            event.outcome,
            "network scope is declared empty",
            event.denials,
        )
    if any(_host_port(entry) == event.target for entry in declared):
        return None
    return Divergence(
        event.kind,
        event.target,
        DivergenceStatus.EXCEEDED,
        event.outcome,
        f"no declared network entry matches {event.target!r}",
        event.denials,
    )


def _shell_divergence(
    event: Event, tools: frozenset[str] | None
) -> Divergence | None:
    if tools is None:
        return Divergence(
            event.kind,
            event.target,
            DivergenceStatus.UNDECLARED,
            event.outcome,
            "no tool scope declared",
            event.denials,
        )
    if any(tool == "Bash" or tool.startswith("Bash(") for tool in tools):
        return None
    return Divergence(
        event.kind,
        event.target,
        DivergenceStatus.EXCEEDED,
        event.outcome,
        "tool scope does not declare Bash",
        event.denials,
    )


def _normalise(path: str) -> str:
    return posixpath.normpath(path)
