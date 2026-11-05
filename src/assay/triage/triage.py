"""The A10 static pre-filter: a queue heuristic, never a verdict."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from assay.ingest import Skill


class Priority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


SIGNALS: tuple[tuple[str, Priority, re.Pattern[str]], ...] = (
    (
        "remote-script",
        Priority.HIGH,
        re.compile(
            r"\b(?:curl|wget)\b[^\n]*\|\s*(?:sudo\s+)?(?:ba|z)?sh\b", re.IGNORECASE
        ),
    ),
    (
        "credentials",
        Priority.HIGH,
        re.compile(
            r"\b(?:api[_-]?key|secret|token|password|passwd|id_rsa|authorized_keys|ssh)\b"
            r"|\.env\b",
            re.IGNORECASE,
        ),
    ),
    (
        "persistence",
        Priority.HIGH,
        re.compile(
            r"\b(?:crontab|launchctl|systemd|systemctl|rc\.local|autostart)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "prompt-injection",
        Priority.HIGH,
        re.compile(
            r"\b(?:ignore\s+(?:all\s+)?previous|system\s+prompt|exfiltrat|"
            r"do\s+not\s+tell|without\s+telling|override\s+your)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "destructive",
        Priority.HIGH,
        re.compile(r"\brm\s+-rf\b|\bdd\b[^\n]*\bof=/dev/|\bmkfs\b", re.IGNORECASE),
    ),
    (
        "privilege",
        Priority.HIGH,
        re.compile(r"\bsudo\b|\bchmod\s+777\b", re.IGNORECASE),
    ),
    (
        "network",
        Priority.MEDIUM,
        re.compile(
            r"\b(?:https?://|curl|wget|fetch|requests\.|httpx|socket)\b", re.IGNORECASE
        ),
    ),
    (
        "shell",
        Priority.MEDIUM,
        re.compile(
            r"\b(?:bash|sh|zsh|fish|exec|eval|system|subprocess|os\.system|child_process)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "filesystem",
        Priority.MEDIUM,
        re.compile(
            r"(?:/etc/|/usr/|/bin/|/private/|~/|\.ssh/|\.aws/|\.config/)",
            re.IGNORECASE,
        ),
    ),
    (
        "install",
        Priority.MEDIUM,
        re.compile(
            r"\b(?:npm|pnpm|yarn|pip|pip3|uv|brew|apt|apt-get|go)\s+"
            r"(?:install|add|get)\b",
            re.IGNORECASE,
        ),
    ),
)

_PRIORITY_RANK = {Priority.LOW: 0, Priority.MEDIUM: 1, Priority.HIGH: 2}


@dataclass(frozen=True, slots=True)
class Triage:
    priority: Priority
    signals: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.priority, Priority):
            raise ValueError(f"priority must be a Priority, got {self.priority!r}")
        signals = tuple(self.signals)
        if isinstance(self.signals, str) or not all(
            isinstance(signal, str) and signal for signal in signals
        ):
            raise ValueError(
                f"signals must be a tuple of non-empty strings, got {self.signals!r}"
            )
        object.__setattr__(self, "signals", tuple(sorted(set(signals))))


def triage(skill: Skill) -> Triage:
    if not isinstance(skill, Skill):
        raise TypeError(f"skill must be a Skill, got {skill!r}")
    text = f"{skill.description}\n{skill.body}"
    matched = {
        label: priority
        for label, priority, pattern in SIGNALS
        if pattern.search(text) is not None
    }
    priority = max(matched.values(), key=_PRIORITY_RANK.__getitem__, default=Priority.LOW)
    return Triage(priority=priority, signals=tuple(matched))
