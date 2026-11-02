from datetime import date
from pathlib import Path

import pytest

from assay.capture import Event, EventKind, EventOutcome, Trace
from assay.corpus import (
    Case,
    Label,
    Metrics,
    Observation,
    Ratio,
    Source,
    evaluate,
    measure,
)
from assay.ingest import parse_skill
from assay.verdict import Assessment, FindingClass, Strictness, UnverifiedCause, Verdict

SKILL_TEXT = """---
name: demo
description: A demo skill.
allowed-tools: Read, Bash
metadata:
  assay:
    files:
      - in.txt
    network: []
---
Do the demo.
"""

RATIO_FIELDS = (
    "malicious_precision",
    "malicious_recall",
    "detection_recall",
    "clean_false_malicious",
    "clean_review",
    "coverage",
)


def obs(
    case_id: str = "case",
    label: Label = Label.MALICIOUS,
    verdict: Verdict = Verdict.CLEAN,
    *,
    cause: UnverifiedCause | None = None,
    labeler: str = "aliz",
    source: Source = Source.SYNTHETIC,
    finding_classes: tuple[FindingClass, ...] = (),
) -> Observation:
    return Observation(
        case_id=case_id,
        label=label,
        labeler=labeler,
        source=source,
        verdict=verdict,
        cause=cause,
        finding_classes=finding_classes,
    )


def dataset() -> list[Observation]:
    return [
        obs("m-malicious", Label.MALICIOUS, Verdict.MALICIOUS),
        obs("m-flagged", Label.MALICIOUS, Verdict.FLAGGED),
        obs("m-clean", Label.MALICIOUS, Verdict.CLEAN),
        obs(
            "m-unverified",
            Label.MALICIOUS,
            Verdict.UNVERIFIED,
            cause=UnverifiedCause.NO_TRIGGER,
        ),
        obs("c-malicious", Label.CLEAN, Verdict.MALICIOUS),
        obs("c-flagged", Label.CLEAN, Verdict.FLAGGED),
        obs("c-clean", Label.CLEAN, Verdict.CLEAN),
        obs(
            "c-unverified",
            Label.CLEAN,
            Verdict.UNVERIFIED,
            cause=UnverifiedCause.AGENT_FAILED,
        ),
    ]


@pytest.mark.parametrize("verdict", [Verdict.MALICIOUS, Verdict.FLAGGED, Verdict.CLEAN])
@pytest.mark.parametrize("label", [Label.MALICIOUS, Label.CLEAN])
def test_confusion_counts_each_verdict_label_cell(verdict, label):
    metrics = measure([obs("case", label, verdict)])
    other = Label.CLEAN if label is Label.MALICIOUS else Label.MALICIOUS

    assert metrics.confusion[verdict][label] == 1
    assert metrics.confusion[verdict][other] == 0
    assert sum(sum(row.values()) for row in metrics.confusion.values()) == 1


def test_confusion_has_three_rows_and_excludes_unverified():
    metrics = measure(
        [obs("u", Label.MALICIOUS, Verdict.UNVERIFIED, cause=UnverifiedCause.NO_TRIGGER)]
    )

    assert set(metrics.confusion) == {Verdict.MALICIOUS, Verdict.FLAGGED, Verdict.CLEAN}
    assert all(row == {Label.MALICIOUS: 0, Label.CLEAN: 0} for row in metrics.confusion.values())


def test_counts_and_every_ratio_use_explicit_numerators_and_denominators():
    metrics = measure(dataset())

    assert metrics.total == 8
    assert metrics.decided == 6
    assert metrics.unverified == 2
    assert metrics.by_label == {Label.MALICIOUS: 4, Label.CLEAN: 4}
    assert metrics.by_label[Label.MALICIOUS] == 4
    assert metrics.by_label[Label.CLEAN] == 4
    assert metrics.malicious_precision == Ratio(1, 2)
    assert metrics.malicious_recall == Ratio(1, 3)
    assert metrics.detection_recall == Ratio(2, 3)
    assert metrics.clean_false_malicious == Ratio(1, 3)
    assert metrics.clean_review == Ratio(1, 3)
    assert metrics.coverage == Ratio(6, 8)
    assert metrics.malicious_precision.value == 0.5
    assert metrics.coverage.value == 0.75


def test_malicious_on_clean_is_a_false_malicious_and_enters_the_precision_denominator():
    metrics = measure(
        [
            obs("false-accusation", Label.CLEAN, Verdict.MALICIOUS),
            obs("true-accusation", Label.MALICIOUS, Verdict.MALICIOUS),
        ]
    )

    assert metrics.false_malicious_cases == ("false-accusation",)
    assert metrics.malicious_precision == Ratio(1, 2)
    assert metrics.clean_false_malicious == Ratio(1, 1)


def test_flagged_on_malicious_counts_for_detection_recall_only():
    metrics = measure(
        [
            obs("detected", Label.MALICIOUS, Verdict.MALICIOUS),
            obs("reviewed", Label.MALICIOUS, Verdict.FLAGGED),
        ]
    )

    assert metrics.malicious_recall == Ratio(1, 2)
    assert metrics.detection_recall == Ratio(2, 2)
    assert metrics.false_negative_cases == ()
    assert metrics.false_malicious_cases == ()


def test_flagged_on_clean_is_review_not_a_false_malicious():
    metrics = measure(
        [
            obs("review", Label.CLEAN, Verdict.FLAGGED),
            obs("clean", Label.CLEAN, Verdict.CLEAN),
        ]
    )

    assert metrics.clean_review == Ratio(1, 2)
    assert metrics.clean_false_malicious == Ratio(0, 2)
    assert metrics.false_malicious_cases == ()
    assert metrics.malicious_precision == Ratio(0, 0)


def test_clean_on_malicious_is_a_false_negative_and_not_a_detection():
    metrics = measure(
        [
            obs("missed-b", Label.MALICIOUS, Verdict.CLEAN),
            obs("missed-a", Label.MALICIOUS, Verdict.CLEAN),
            obs("caught", Label.MALICIOUS, Verdict.MALICIOUS),
        ]
    )

    assert metrics.false_negative_cases == ("missed-a", "missed-b")
    assert metrics.malicious_recall == Ratio(1, 3)
    assert metrics.detection_recall == Ratio(1, 3)


def test_unverified_is_excluded_from_ratios_and_counted_by_every_cause():
    observations = [
        obs(f"u-{index}", Label.MALICIOUS, Verdict.UNVERIFIED, cause=cause)
        for index, cause in enumerate(UnverifiedCause)
    ]
    observations.append(obs("decided", Label.MALICIOUS, Verdict.MALICIOUS))

    metrics = measure(observations)

    assert metrics.total == 6
    assert metrics.decided == 1
    assert metrics.unverified == 5
    assert metrics.unverified_by_cause == {cause: 1 for cause in UnverifiedCause}
    assert sum(sum(row.values()) for row in metrics.confusion.values()) == 1
    assert metrics.malicious_recall == Ratio(1, 1)
    assert metrics.detection_recall == Ratio(1, 1)
    assert metrics.coverage == Ratio(1, 6)


def test_unverified_by_cause_always_contains_all_five_keys():
    metrics = measure([obs("clean", Label.CLEAN, Verdict.CLEAN)])

    assert set(metrics.unverified_by_cause) == set(UnverifiedCause)
    assert set(metrics.unverified_by_cause.values()) == {0}


def test_ratio_value_is_none_only_for_a_zero_denominator():
    assert Ratio(1, 2).value == 0.5
    assert Ratio(0, 5).value == 0.0
    assert Ratio(0, 0).value is None


def test_zero_denominators_are_none_not_zero():
    no_malicious_verdict = measure([obs("clean", Label.CLEAN, Verdict.CLEAN)])
    assert no_malicious_verdict.malicious_precision == Ratio(0, 0)
    assert no_malicious_verdict.malicious_precision.value is None

    no_decided_malicious = measure([obs("clean", Label.CLEAN, Verdict.FLAGGED)])
    for field in ("malicious_recall", "detection_recall"):
        ratio = getattr(no_decided_malicious, field)
        assert ratio.denominator == 0
        assert ratio.value is None

    no_decided_clean = measure([obs("bad", Label.MALICIOUS, Verdict.CLEAN)])
    for field in ("clean_false_malicious", "clean_review"):
        ratio = getattr(no_decided_clean, field)
        assert ratio.denominator == 0
        assert ratio.value is None


def test_measure_of_nothing_is_all_zeros_and_none():
    metrics = measure([])

    assert isinstance(metrics, Metrics)
    assert metrics.total == 0
    assert metrics.by_label == {Label.MALICIOUS: 0, Label.CLEAN: 0}
    assert metrics.decided == 0
    assert metrics.unverified == 0
    assert metrics.unverified_by_cause == {cause: 0 for cause in UnverifiedCause}
    assert metrics.confusion == {
        Verdict.MALICIOUS: {Label.MALICIOUS: 0, Label.CLEAN: 0},
        Verdict.FLAGGED: {Label.MALICIOUS: 0, Label.CLEAN: 0},
        Verdict.CLEAN: {Label.MALICIOUS: 0, Label.CLEAN: 0},
    }
    assert metrics.false_malicious_cases == ()
    assert metrics.false_negative_cases == ()
    assert metrics.cases == ()
    assert metrics.labelers == {}
    assert metrics.sources == {}
    for field in RATIO_FIELDS:
        assert getattr(metrics, field).value is None


def test_payload_has_the_documented_keys_and_sorted_cases():
    metrics = measure(
        [
            obs(
                "z-case",
                Label.CLEAN,
                Verdict.MALICIOUS,
                labeler="bob",
                source=Source.LOCAL_MODEL,
                finding_classes=(
                    FindingClass.UNDECLARED_NETWORK,
                    FindingClass.SHELL,
                    FindingClass.SHELL,
                ),
            ),
            obs(
                "a-case",
                Label.MALICIOUS,
                Verdict.UNVERIFIED,
                cause=UnverifiedCause.COST_CAPPED,
                labeler="aliz",
            ),
        ]
    )

    payload = metrics.to_payload()

    assert set(payload) == {
        "total",
        "by_label",
        "decided",
        "unverified",
        "unverified_by_cause",
        "confusion",
        "malicious_precision",
        "malicious_recall",
        "detection_recall",
        "clean_false_malicious",
        "clean_review",
        "coverage",
        "false_malicious_cases",
        "false_negative_cases",
        "labelers",
        "sources",
        "cases",
    }
    assert payload["total"] == 2
    assert payload["by_label"] == {"malicious": 1, "clean": 1}
    assert payload["decided"] == 1
    assert payload["unverified"] == 1
    assert payload["unverified_by_cause"] == {
        "no-trigger": 0,
        "no-declared-scope": 0,
        "agent-failed": 0,
        "budget-limit": 0,
        "cost-capped": 1,
    }
    assert payload["confusion"] == {
        "malicious": {"malicious": 0, "clean": 1},
        "flagged": {"malicious": 0, "clean": 0},
        "clean": {"malicious": 0, "clean": 0},
    }
    assert payload["malicious_precision"] == {
        "numerator": 0,
        "denominator": 1,
        "value": 0.0,
    }
    assert payload["malicious_recall"] == {
        "numerator": 0,
        "denominator": 0,
        "value": None,
    }
    assert payload["detection_recall"] == {
        "numerator": 0,
        "denominator": 0,
        "value": None,
    }
    assert payload["clean_false_malicious"] == {
        "numerator": 1,
        "denominator": 1,
        "value": 1.0,
    }
    assert payload["clean_review"] == {
        "numerator": 0,
        "denominator": 1,
        "value": 0.0,
    }
    assert payload["coverage"] == {"numerator": 1, "denominator": 2, "value": 0.5}
    assert payload["false_malicious_cases"] == ["z-case"]
    assert payload["false_negative_cases"] == []
    assert payload["labelers"] == {"aliz": 1, "bob": 1}
    assert payload["sources"] == {"local-model": 1, "synthetic": 1}
    assert payload["cases"] == [
        {
            "id": "a-case",
            "label": "malicious",
            "labeler": "aliz",
            "source": "synthetic",
            "verdict": "unverified",
            "cause": "cost-capped",
            "finding_classes": [],
        },
        {
            "id": "z-case",
            "label": "clean",
            "labeler": "bob",
            "source": "local-model",
            "verdict": "malicious",
            "cause": None,
            "finding_classes": ["shell", "undeclared-network"],
        },
    ]


def make_case(
    tmp_path: Path,
    case_id: str,
    *,
    label: Label = Label.MALICIOUS,
    strictness: Strictness = Strictness.STANDARD,
    events=(),
) -> Case:
    directory = tmp_path / case_id
    directory.mkdir()
    (directory / "SKILL.md").write_text(SKILL_TEXT, encoding="utf-8")
    skill = parse_skill(directory / "SKILL.md")
    trace = Trace(
        skill_name=skill.name,
        skill_content_hash=skill.content_hash,
        task_sha256="b" * 64,
        cause=None,
        input_tokens=0,
        output_tokens=0,
        cost_usd=0.0,
        events=events,
        sandbox_config_hashes=(),
    )
    return Case(
        id=case_id,
        label=label,
        labeler="aliz",
        labeled_at=date(2026, 11, 3),
        rationale="A test case.",
        source=Source.SYNTHETIC,
        strictness=strictness,
        skill=skill,
        trace=trace,
        expected_classes=(),
        path=directory,
    )


def test_evaluate_passes_each_case_strictness_to_assess(tmp_path, monkeypatch):
    cases = [
        make_case(tmp_path, "strict-case", label=Label.CLEAN, strictness=Strictness.STRICT),
        make_case(
            tmp_path, "baseline-case", label=Label.MALICIOUS, strictness=Strictness.BASELINE
        ),
    ]
    levels = []

    def fake_assess(skill, trace, *, policy):
        levels.append(policy.level)
        return Assessment(
            verdict=Verdict.CLEAN,
            findings=(),
            cause=None,
            blocked=False,
            strictness=policy.level,
            skill_content_hash=skill.content_hash,
            trace_hash=trace.hash,
        )

    monkeypatch.setattr("assay.corpus.metrics.assess", fake_assess)

    metrics = evaluate(cases)

    assert levels == [Strictness.STRICT, Strictness.BASELINE]
    assert [observation.case_id for observation in metrics.cases] == [
        "baseline-case",
        "strict-case",
    ]
    assert all(observation.verdict is Verdict.CLEAN for observation in metrics.cases)


def test_evaluate_uses_the_shipped_assess_for_verdicts_and_findings(tmp_path):
    case = make_case(
        tmp_path,
        "shell-case",
        events=(
            Event(
                kind=EventKind.SHELL,
                outcome=EventOutcome.OK,
                target="rm -rf /",
                content_sha256="d" * 64,
                content_bytes=7,
                excerpt="rm -rf /",
            ),
        ),
    )

    metrics = evaluate([case])

    assert metrics.cases[0].verdict is Verdict.MALICIOUS
    assert FindingClass.SHELL in metrics.cases[0].finding_classes
    assert metrics.false_negative_cases == ()


def test_evaluate_keeps_an_unverified_cause(tmp_path):
    case = make_case(tmp_path, "silent-case")

    metrics = evaluate([case])

    assert metrics.cases[0].verdict is Verdict.UNVERIFIED
    assert metrics.cases[0].cause is UnverifiedCause.NO_TRIGGER
    assert metrics.unverified_by_cause[UnverifiedCause.NO_TRIGGER] == 1
