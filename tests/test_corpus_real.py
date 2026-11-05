"""The private real-world control: own Plumb skills, one local-model run each."""

from pathlib import Path

from assay.corpus import Label, Source, evaluate, load_corpus

REPO = Path(__file__).resolve().parents[1]
REAL = REPO / "corpus" / "real"


def test_the_real_control_loads_eight_clean_local_model_cases():
    cases = load_corpus(REAL)

    assert len(cases) == 8
    assert all(case.source is Source.LOCAL_MODEL for case in cases)
    assert all(case.label is Label.CLEAN for case in cases)
    assert all(case.trace.schema == 2 for case in cases)
    assert all(case.trace.skill_content_hash == case.skill.content_hash for case in cases)


def test_the_real_control_has_no_false_malicious():
    metrics = evaluate(load_corpus(REAL))

    assert metrics.total == 8
    assert metrics.false_malicious_cases == ()
