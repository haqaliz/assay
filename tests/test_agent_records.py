from dataclasses import FrozenInstanceError

import pytest

from assay.agent import (
    AgentError,
    AgentUnavailable,
    Budget,
    ModelFailed,
    ModelPrice,
    RunCause,
    RunOutcome,
    ToolAction,
    ToolCall,
    ToolResult,
    Usage,
)


def test_non_finite_budget_and_price_values_are_rejected():
    for bad in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValueError):
            Budget(max_usd=bad)
        with pytest.raises(ValueError):
            Budget(max_usd=1.0, max_wall_seconds=bad)
        with pytest.raises(ValueError):
            ModelPrice(input_per_mtok=bad, output_per_mtok=1.0)


def test_max_actions_must_be_positive():
    for bad in (0, -1, True):
        with pytest.raises(ValueError):
            Budget(max_usd=1.0, max_actions=bad)


def test_run_cause_is_the_closed_seven_name_set():
    assert {c.name for c in RunCause} == {
        "MISSING_KEY",
        "MODEL_FAILED",
        "COST_CAPPED",
        "STEP_LIMIT",
        "ACTION_LIMIT",
        "WALL_LIMIT",
        "SANDBOX_UNAVAILABLE",
    }


def test_usage_adds_token_wise():
    total = Usage(input_tokens=3, output_tokens=4) + Usage(input_tokens=1, output_tokens=2)
    assert total == Usage(input_tokens=4, output_tokens=6)


@pytest.mark.parametrize("field", ["input_tokens", "output_tokens"])
def test_usage_rejects_negative_and_bool_tokens(field):
    with pytest.raises(ValueError, match=field):
        Usage(**{field: -1})
    with pytest.raises(ValueError, match=field):
        Usage(**{field: True})


def test_price_cost_is_per_million_tokens():
    price = ModelPrice(input_per_mtok=3.0, output_per_mtok=15.0)
    assert price.cost(Usage(input_tokens=1_000_000, output_tokens=1_000_000)) == 18.0
    assert price.cost(Usage(input_tokens=1500, output_tokens=300)) == pytest.approx(
        1500 / 1e6 * 3.0 + 300 / 1e6 * 15.0
    )


@pytest.mark.parametrize("field", ["input_per_mtok", "output_per_mtok"])
def test_price_rejects_negative_and_bool(field):
    valid = {"input_per_mtok": 1.0, "output_per_mtok": 1.0}
    with pytest.raises(ValueError, match=field):
        ModelPrice(**(valid | {field: -0.1}))
    with pytest.raises(ValueError, match=field):
        ModelPrice(**(valid | {field: False}))


def test_budget_defaults_and_explicit_max_usd():
    budget = Budget(max_usd=2.5)
    assert budget.max_steps == 20
    assert budget.max_wall_seconds == 300.0


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_usd": 0},
        {"max_usd": -1.0},
        {"max_usd": True},
        {"max_usd": 1.0, "max_steps": 0},
        {"max_usd": 1.0, "max_steps": True},
        {"max_usd": 1.0, "max_wall_seconds": 0},
        {"max_usd": 1.0, "max_wall_seconds": -1.0},
        {"max_usd": 1.0, "max_wall_seconds": True},
    ],
)
def test_budget_rejects_non_positive_or_bool_values(kwargs):
    with pytest.raises(ValueError):
        Budget(**kwargs)


def test_outcome_is_finished_only_without_cause_and_with_final_text():
    base = dict(steps=1, actions=(), usage=Usage(), cost_usd=0.0)
    assert RunOutcome(cause=None, final_text="done", **base).finished
    assert not RunOutcome(cause=None, final_text=None, **base).finished
    assert not RunOutcome(cause=RunCause.STEP_LIMIT, final_text="x", **base).finished


def test_tool_records_carry_the_call_result_and_optional_sandbox_record():
    call = ToolCall(id="t1", name="read_file", arguments={"path": "a.txt"})
    result = ToolResult(ok=False, output="denied")
    action = ToolAction(call=call, result=result)
    assert action.call is call
    assert action.result.record is None
    assert not action.result.ok


def test_agent_errors_are_named_and_unavailable_carries_a_cause():
    assert issubclass(AgentUnavailable, AgentError)
    assert issubclass(ModelFailed, AgentError)
    err = AgentUnavailable("no key", cause=RunCause.MISSING_KEY)
    assert err.cause is RunCause.MISSING_KEY
    assert "no key" in str(err)


def test_records_are_frozen():
    usage = Usage()
    with pytest.raises(FrozenInstanceError):
        usage.input_tokens = 1  # type: ignore[misc]
