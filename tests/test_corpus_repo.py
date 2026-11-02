from pathlib import Path

from assay.corpus import Label, Source, evaluate, load_corpus
from assay.verdict import StrictnessPolicy, UnverifiedCause, Verdict, assess

REPO = Path(__file__).resolve().parents[1]
CASES = REPO / "corpus"


def test_repo_corpus_loads_at_least_sixteen_cases_with_both_labels_and_sources():
    cases = load_corpus(CASES)
    assert len(cases) >= 16
    assert sum(case.label is Label.MALICIOUS for case in cases) >= 8
    assert sum(case.label is Label.CLEAN for case in cases) >= 8
    assert {case.source for case in cases} == set(Source)


def test_every_unverified_cause_appears():
    by_cause = evaluate(load_corpus(CASES)).unverified_by_cause
    assert all(by_cause[cause] > 0 for cause in UnverifiedCause)


def test_ratios_have_nonzero_denominators():
    metrics = evaluate(load_corpus(CASES))
    assert metrics.malicious_precision.denominator > 0
    assert metrics.malicious_recall.denominator > 0
    assert metrics.clean_false_malicious.denominator > 0


def test_the_desktop_write_and_plumb_report_regressions_are_not_malicious():
    cases = {case.id: case for case in load_corpus(CASES)}
    for case_id in ("synthetic-desktop-write-review", "plumb-report-desktop-write"):
        case = cases[case_id]
        assessment = assess(
            case.skill, case.trace, policy=StrictnessPolicy(level=case.strictness)
        )
        assert assessment.verdict is not Verdict.MALICIOUS


def test_every_case_trace_is_schema_two_and_matches_its_skill():
    for case in load_corpus(CASES):
        assert case.trace.schema == 2
        assert case.trace.skill_content_hash == case.skill.content_hash
