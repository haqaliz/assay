import pytest

from assay.verdict import FindingClass, Severity, Strictness
from assay.verdict.policy import DEFAULT_POLICY, FLOOR, FloorViolation, StrictnessPolicy


def test_default_policy_is_standard_with_a_review_floor_for_all_four_classes():
    assert DEFAULT_POLICY.level is Strictness.STANDARD
    assert DEFAULT_POLICY.floors == {class_: Severity.REVIEW for class_ in FindingClass}
    assert [DEFAULT_POLICY.floor(class_) for class_ in FindingClass] == [Severity.REVIEW] * 4
    assert FLOOR == {class_: Severity.REVIEW for class_ in FindingClass}


def test_a_floor_lowered_to_low_is_refused():
    with pytest.raises(FloorViolation, match="undeclared-file"):
        StrictnessPolicy(floors={**FLOOR, FindingClass.UNDECLARED_FILE: Severity.LOW})


def test_a_missing_floor_class_is_refused():
    floors = dict(FLOOR)
    del floors[FindingClass.SHELL]

    with pytest.raises(FloorViolation, match="exactly"):
        StrictnessPolicy(floors=floors)


@pytest.mark.parametrize(
    "floors",
    [
        {class_.value: Severity.REVIEW for class_ in FindingClass},
        {**FLOOR, "not-a-class": Severity.REVIEW},
    ],
)
def test_an_unknown_floor_class_is_refused(floors):
    with pytest.raises(FloorViolation, match="exactly"):
        StrictnessPolicy(floors=floors)


def test_the_instructions_floor_cannot_exceed_review():
    with pytest.raises(FloorViolation, match="INSTRUCTIONS"):
        StrictnessPolicy(floors={**FLOOR, FindingClass.INSTRUCTIONS: Severity.HIGH})


@pytest.mark.parametrize("level", ["strict", "banana"])
def test_a_bad_strictness_level_is_refused(level):
    with pytest.raises(FloorViolation, match="level"):
        StrictnessPolicy(level=level)


def test_a_class_may_be_raised_to_high_and_the_rest_stay_at_review():
    policy = StrictnessPolicy(
        level=Strictness.STRICT, floors={**FLOOR, FindingClass.SHELL: Severity.HIGH}
    )

    assert policy.level is Strictness.STRICT
    assert policy.floor(FindingClass.SHELL) is Severity.HIGH
    assert policy.floor(FindingClass.UNDECLARED_FILE) is Severity.REVIEW


def test_a_floor_value_must_be_a_severity():
    with pytest.raises(FloorViolation, match="shell"):
        StrictnessPolicy(floors={**FLOOR, FindingClass.SHELL: "high"})


def test_the_floor_and_a_policys_floors_cannot_be_mutated():
    with pytest.raises(TypeError):
        FLOOR[FindingClass.SHELL] = Severity.HIGH  # type: ignore[index]
    with pytest.raises(TypeError):
        DEFAULT_POLICY.floors[FindingClass.SHELL] = Severity.HIGH  # type: ignore[index]
