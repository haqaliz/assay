from pathlib import Path

from assay.corpus import Label, Ratio, evaluate, load_corpus
from assay.verdict import Verdict

REPO = Path(__file__).resolve().parents[1]
HELDOUT = REPO / "corpus" / "heldout"
DEVELOPMENT = REPO / "corpus"


def test_the_heldout_calibration_metrics_are_fully_detected_without_a_false_accusation():
    metrics = evaluate(load_corpus(HELDOUT))

    assert metrics.total == 8
    assert metrics.by_label[Label.MALICIOUS] == 4
    assert metrics.by_label[Label.CLEAN] == 4
    assert metrics.malicious_precision == Ratio(4, 4)
    assert metrics.malicious_recall == Ratio(4, 4)
    assert metrics.detection_recall == Ratio(4, 4)
    assert metrics.clean_false_malicious == Ratio(0, 4)
    assert metrics.clean_review == Ratio(0, 4)
    assert metrics.coverage == Ratio(8, 8)


def test_the_heldout_cases_get_the_expected_verdict():
    verdicts = {
        observation.case_id: observation.verdict
        for observation in evaluate(load_corpus(HELDOUT)).cases
    }

    assert verdicts == {
        "heldout-chmod-local": Verdict.CLEAN,
        "heldout-dd-disk": Verdict.MALICIOUS,
        "heldout-dd-null": Verdict.CLEAN,
        "heldout-dev-tcp": Verdict.MALICIOUS,
        "heldout-python-print": Verdict.CLEAN,
        "heldout-python-pty": Verdict.MALICIOUS,
        "heldout-socat-server": Verdict.CLEAN,
        "heldout-socat-shell": Verdict.MALICIOUS,
    }


def test_the_development_corpus_metrics_are_unchanged():
    metrics = evaluate(load_corpus(DEVELOPMENT))

    assert metrics.total == 20
    assert metrics.malicious_precision == Ratio(5, 5)
    assert metrics.malicious_recall == Ratio(5, 7)
    assert metrics.detection_recall == Ratio(7, 7)
    assert metrics.clean_false_malicious == Ratio(0, 6)
    assert metrics.clean_review == Ratio(2, 6)
    assert metrics.coverage == Ratio(13, 20)
