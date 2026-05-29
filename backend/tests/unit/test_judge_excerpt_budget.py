"""Judge excerpt sizing vs run budget."""

from __future__ import annotations

import pytest

from app.ai.agents.judge import EXCERPT_MAX_CHARS, _excerpt_max_chars
from app.ai.budget import TokenBudget


@pytest.mark.unit
def test_excerpt_max_shrinks_with_many_insights() -> None:
    budget = TokenBudget(limit=200_000, judge_reserve=90_000)
    budget.record(input_tokens=91_064, output_tokens=0)
    assert budget.remaining(for_judge=True) == 108_936
    assert _excerpt_max_chars(budget, insight_count=36) < EXCERPT_MAX_CHARS
    assert _excerpt_max_chars(budget, insight_count=36) <= 8_000


@pytest.mark.unit
def test_excerpt_max_allows_full_window_for_few_insights() -> None:
    budget = TokenBudget(limit=200_000, judge_reserve=90_000)
    budget.record(input_tokens=50_000, output_tokens=0)
    assert _excerpt_max_chars(budget, insight_count=5) == EXCERPT_MAX_CHARS
