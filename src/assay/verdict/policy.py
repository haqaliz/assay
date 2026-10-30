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
        if not isinstance(self.floors, Mapping):
            raise FloorViolation(f"floors must be a mapping, got {self.floors!r}")
        floors = dict(self.floors)
        if set(floors) != set(FindingClass) or not all(
            isinstance(class_, FindingClass) for class_ in floors
        ):
            raise FloorViolation(
                f"floors must contain exactly {sorted(FindingClass, key=str)}, "
                f"got {sorted(floors, key=str)}"
            )
        # The floor is fixed for now: raising it is not implemented (the level raises strictness),
        # and lowering it is forbidden by the contract.
        for class_, severity in floors.items():
            if severity is not FLOOR[class_]:
                raise FloorViolation(
                    f"{class_} floor is fixed at {FLOOR[class_]}, got {severity!r}; "
                    "raise strictness with a level instead"
                )
        object.__setattr__(self, "floors", MappingProxyType(floors))

    def floor(self, class_: FindingClass) -> Severity:
        return self.floors[class_]


DEFAULT_POLICY = StrictnessPolicy()
