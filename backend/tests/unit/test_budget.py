"""Token budget tests."""

from __future__ import annotations

import pytest

from app.ai.budget import TokenBudget, TokenBudgetExceeded


@pytest.mark.unit
def test_records_and_reports_remaining() -> None:
    b = TokenBudget(limit=1000)
    assert b.remaining() == 1000
    b.record(input_tokens=300, output_tokens=200)
    assert b.remaining() == 500


@pytest.mark.unit
def test_guard_raises_when_exceeded() -> None:
    b = TokenBudget(limit=100)
    b.record(input_tokens=60, output_tokens=50)
    assert b.exceeded()
    with pytest.raises(TokenBudgetExceeded):
        b.guard()


@pytest.mark.unit
def test_guard_passes_when_within_budget() -> None:
    b = TokenBudget(limit=100)
    b.record(input_tokens=10, output_tokens=10)
    b.guard()  # must not raise


@pytest.mark.unit
def test_negative_values_clamped_to_zero() -> None:
    b = TokenBudget(limit=100)
    b.record(input_tokens=-5, output_tokens=-5)
    assert b.remaining() == 100


@pytest.mark.unit
def test_judge_reserve_limits_main_phase() -> None:
    b = TokenBudget(limit=1000, judge_reserve=200)
    b.record(input_tokens=850, output_tokens=0)
    with pytest.raises(TokenBudgetExceeded):
        b.guard(for_judge=False)
    b.guard(for_judge=True)  # can still spend up to full limit


@pytest.mark.unit
def test_judge_reserve_blocks_judge_when_fully_spent() -> None:
    b = TokenBudget(limit=1000, judge_reserve=200)
    b.record(input_tokens=1000, output_tokens=0)
    with pytest.raises(TokenBudgetExceeded):
        b.guard(for_judge=True)
