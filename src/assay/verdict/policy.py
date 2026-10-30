"""Strictness levels and the severity floor that no policy may lower."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping

from .records import FindingClass, Severity, Strictness, VerdictError

FLOOR: Mapping[FindingClass, Severity] = MappingProxyType(
    {class_: Severity.REVIEW for class_ in FindingClass}
)


class FloorViolation(VerdictError):
    """A policy tried to lower or reshape the floor; refused at construction."""


@dataclass(frozen=True, slots=True)
class StrictnessPolicy:
    level: Strictness = Strictness.STANDARD
    floors: Mapping[FindingClass, Severity] = field(default_factory=lambda: dict(FLOOR))

    def __post_init__(self) -> None:
        if not isinstance(self.level, Strictness):
            raise FloorViolation(f"level must be a Strictness, got {self.level!r}")
        if set(self.floors) != set(FindingClass) or not all(
            isinstance(class_, FindingClass) for class_ in self.floors
        ):
            raise FloorViolation(
                f"floors must contain exactly {sorted(FindingClass)}, got {sorted(self.floors)}"
            )
        for class_, severity in self.floors.items():
            floor = FLOOR[class_]
            if not isinstance(severity, Severity) or severity.rank < floor.rank:
                raise FloorViolation(f"{class_} floor cannot be below {floor}, got {severity!r}")
            if class_ is FindingClass.INSTRUCTIONS and severity is not Severity.REVIEW:
                raise FloorViolation(
                    f"INSTRUCTIONS floor is capped at {Severity.REVIEW}, got {severity!r}"
                )
        object.__setattr__(self, "floors", MappingProxyType(dict(self.floors)))

    def floor(self, class_: FindingClass) -> Severity:
        return self.floors[class_]


DEFAULT_POLICY = StrictnessPolicy()
