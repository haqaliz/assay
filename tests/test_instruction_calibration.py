from pathlib import Path

from assay.corpus import Label, evaluate, load_corpus
from assay.verdict import (
    FindingClass,
    Severity,
    StrictnessPolicy,
    Verdict,
    assess,
)

REPO = Path(__file__).resolve().parents[1]
HELDOUT = REPO / "corpus" / "heldout-instructions"
MAIN = REPO / "corpus"


def assessments(root):
    return {
        case.id: assess(
            case.skill, case.trace, policy=StrictnessPolicy(level=case.strictness)
        )
        for case in load_corpus(root)
    }


def test_heldout_instruction_cases_flag_every_attack_and_clear_every_guard():
    cases = load_corpus(HELDOUT)
    results = assessments(HELDOUT)
    malicious = [case for case in cases if case.label is Label.MALICIOUS]
    clean = [case for case in cases if case.label is Label.CLEAN]

    assert len(cases) == 8
    assert len(malicious) == len(clean) == 4
    for case in malicious:
        assert results[case.id].verdict is Verdict.FLAGGED
        assert {finding.class_ for finding in results[case.id].findings} == {
            FindingClass.INSTRUCTIONS
        }
    for case in clean:
        assert results[case.id].verdict is Verdict.CLEAN
        assert results[case.id].findings == ()

    assert all(result.verdict is not Verdict.MALICIOUS for result in results.values())
    assert all(
        finding.severity is Severity.REVIEW
        for result in results.values()
        for finding in result.findings
    )


def test_heldout_instruction_metrics_after_calibration():
    metrics = evaluate(load_corpus(HELDOUT))

    assert (metrics.detection_recall.numerator, metrics.detection_recall.denominator) == (4, 4)
    assert (metrics.malicious_recall.numerator, metrics.malicious_recall.denominator) == (0, 4)
    assert (metrics.clean_review.numerator, metrics.clean_review.denominator) == (0, 4)
    assert (metrics.clean_false_malicious.numerator, metrics.clean_false_malicious.denominator) == (
        0,
        4,
    )
    assert metrics.false_malicious_cases == ()


def test_main_corpus_metrics_are_unchanged_by_the_instruction_calibration():
    metrics = evaluate(load_corpus(MAIN))

    assert metrics.total == 20
    assert (metrics.malicious_precision.numerator, metrics.malicious_precision.denominator) == (
        5,
        5,
    )
    assert (metrics.malicious_recall.numerator, metrics.malicious_recall.denominator) == (5, 7)
    assert (metrics.detection_recall.numerator, metrics.detection_recall.denominator) == (7, 7)
    assert (metrics.clean_false_malicious.numerator, metrics.clean_false_malicious.denominator) == (
        0,
        6,
    )
    assert (metrics.clean_review.numerator, metrics.clean_review.denominator) == (2, 6)
    assert (metrics.coverage.numerator, metrics.coverage.denominator) == (13, 20)
