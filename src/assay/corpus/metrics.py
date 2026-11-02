"""Pure statistics over labeled observations and corpus evaluation."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from assay.verdict import (
    FindingClass,
    StrictnessPolicy,
    UnverifiedCause,
    Verdict,
    assess,
)

from .records import Case, Label, Source

_CONFUSION_ROWS = (Verdict.MALICIOUS, Verdict.FLAGGED, Verdict.CLEAN)


@dataclass(frozen=True, slots=True)
class Observation:
    case_id: str
    label: Label
    labeler: str
    source: Source
    verdict: Verdict
    cause: UnverifiedCause | None
    finding_classes: tuple[FindingClass, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.case_id, str) or not self.case_id:
            raise ValueError(f"case_id must be a non-empty string, got {self.case_id!r}")
        if not isinstance(self.label, Label):
            raise ValueError(f"label must be a Label, got {self.label!r}")
        if not isinstance(self.labeler, str) or not self.labeler:
            raise ValueError(f"labeler must be a non-empty string, got {self.labeler!r}")
        if not isinstance(self.source, Source):
            raise ValueError(f"source must be a Source, got {self.source!r}")
        if not isinstance(self.verdict, Verdict):
            raise ValueError(f"verdict must be a Verdict, got {self.verdict!r}")
        if self.cause is not None and not isinstance(self.cause, UnverifiedCause):
            raise ValueError(f"cause must be an UnverifiedCause or None, got {self.cause!r}")
        if (self.verdict is Verdict.UNVERIFIED) != (self.cause is not None):
            raise ValueError(
                "verdict UNVERIFIED iff cause is set, "
                f"got verdict={self.verdict!r} cause={self.cause!r}"
            )
        classes = tuple(self.finding_classes)
        if not all(isinstance(class_, FindingClass) for class_ in classes):
            raise ValueError("finding_classes must be FindingClass values")
        object.__setattr__(self, "finding_classes", classes)


@dataclass(frozen=True, slots=True)
class Ratio:
    numerator: int
    denominator: int

    @property
    def value(self) -> float | None:
        return None if self.denominator == 0 else self.numerator / self.denominator


@dataclass(frozen=True, slots=True)
class Metrics:
    total: int
    by_label: dict[Label, int]
    decided: int
    unverified: int
    unverified_by_cause: dict[UnverifiedCause, int]
    confusion: dict[Verdict, dict[Label, int]]
    malicious_precision: Ratio
    malicious_recall: Ratio
    detection_recall: Ratio
    clean_false_malicious: Ratio
    clean_review: Ratio
    coverage: Ratio
    false_malicious_cases: tuple[str, ...]
    false_negative_cases: tuple[str, ...]
    labelers: dict[str, int]
    sources: dict[Source, int]
    cases: tuple[Observation, ...]

    def to_payload(self) -> dict[str, object]:
        return {
            "total": self.total,
            "by_label": {label.value: self.by_label[label] for label in Label},
            "decided": self.decided,
            "unverified": self.unverified,
            "unverified_by_cause": {
                cause.value: self.unverified_by_cause[cause] for cause in UnverifiedCause
            },
            "confusion": {
                verdict.value: {label.value: self.confusion[verdict][label] for label in Label}
                for verdict in _CONFUSION_ROWS
            },
            "malicious_precision": _ratio_payload(self.malicious_precision),
            "malicious_recall": _ratio_payload(self.malicious_recall),
            "detection_recall": _ratio_payload(self.detection_recall),
            "clean_false_malicious": _ratio_payload(self.clean_false_malicious),
            "clean_review": _ratio_payload(self.clean_review),
            "coverage": _ratio_payload(self.coverage),
            "false_malicious_cases": list(self.false_malicious_cases),
            "false_negative_cases": list(self.false_negative_cases),
            "labelers": dict(sorted(self.labelers.items())),
            "sources": {
                source.value: self.sources[source]
                for source in sorted(self.sources, key=lambda item: item.value)
            },
            "cases": [
                {
                    "id": observation.case_id,
                    "label": observation.label.value,
                    "labeler": observation.labeler,
                    "source": observation.source.value,
                    "verdict": observation.verdict.value,
                    "cause": observation.cause.value
                    if observation.cause is not None
                    else None,
                    "finding_classes": sorted(
                        {class_.value for class_ in observation.finding_classes}
                    ),
                }
                for observation in sorted(self.cases, key=lambda item: item.case_id)
            ],
        }


def measure(observations: Sequence[Observation]) -> Metrics:
    observations = tuple(observations)
    by_label = {label: 0 for label in Label}
    decided_by_label = {label: 0 for label in Label}
    by_cause = {cause: 0 for cause in UnverifiedCause}
    confusion = {verdict: {label: 0 for label in Label} for verdict in _CONFUSION_ROWS}
    labelers: Counter[str] = Counter()
    sources: Counter[Source] = Counter()
    false_malicious: list[str] = []
    false_negative: list[str] = []
    decided = 0
    for observation in observations:
        by_label[observation.label] += 1
        labelers[observation.labeler] += 1
        sources[observation.source] += 1
        if observation.verdict is Verdict.UNVERIFIED:
            by_cause[observation.cause] += 1
            continue
        decided += 1
        decided_by_label[observation.label] += 1
        confusion[observation.verdict][observation.label] += 1
        if observation.verdict is Verdict.MALICIOUS and observation.label is Label.CLEAN:
            false_malicious.append(observation.case_id)
        if observation.verdict is Verdict.CLEAN and observation.label is Label.MALICIOUS:
            false_negative.append(observation.case_id)
    malicious = confusion[Verdict.MALICIOUS]
    flagged = confusion[Verdict.FLAGGED]
    return Metrics(
        total=len(observations),
        by_label=by_label,
        decided=decided,
        unverified=sum(by_cause.values()),
        unverified_by_cause=by_cause,
        confusion=confusion,
        malicious_precision=Ratio(
            malicious[Label.MALICIOUS],
            malicious[Label.MALICIOUS] + malicious[Label.CLEAN],
        ),
        malicious_recall=Ratio(
            malicious[Label.MALICIOUS], decided_by_label[Label.MALICIOUS]
        ),
        detection_recall=Ratio(
            malicious[Label.MALICIOUS] + flagged[Label.MALICIOUS],
            decided_by_label[Label.MALICIOUS],
        ),
        clean_false_malicious=Ratio(
            malicious[Label.CLEAN], decided_by_label[Label.CLEAN]
        ),
        clean_review=Ratio(flagged[Label.CLEAN], decided_by_label[Label.CLEAN]),
        coverage=Ratio(decided, len(observations)),
        false_malicious_cases=tuple(sorted(false_malicious)),
        false_negative_cases=tuple(sorted(false_negative)),
        labelers=dict(sorted(labelers.items())),
        sources=dict(sorted(sources.items(), key=lambda item: item[0].value)),
        cases=tuple(sorted(observations, key=lambda observation: observation.case_id)),
    )


def evaluate(cases: Sequence[Case]) -> Metrics:
    observations = []
    for case in cases:
        assessment = assess(
            case.skill,
            case.trace,
            policy=StrictnessPolicy(level=case.strictness),
        )
        observations.append(
            Observation(
                case_id=case.id,
                label=case.label,
                labeler=case.labeler,
                source=case.source,
                verdict=assessment.verdict,
                cause=assessment.cause,
                finding_classes=tuple(finding.class_ for finding in assessment.findings),
            )
        )
    return measure(observations)


def _ratio_payload(ratio: Ratio) -> dict[str, object]:
    return {
        "numerator": ratio.numerator,
        "denominator": ratio.denominator,
        "value": ratio.value,
    }
