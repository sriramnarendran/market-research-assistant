"""Recency helpers."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.ai.recency import (
    enhance_search_query,
    fact_recency_score,
    sort_facts_by_recency,
    tavily_search_kwargs,
)
from app.core.config import Settings
from app.ai.schemas import Fact


@pytest.mark.unit
def test_tavily_search_kwargs_uses_90_day_window() -> None:
    settings = Settings(TAVILY_SEARCH_DAYS=90, TAVILY_TIME_RANGE=None)
    assert tavily_search_kwargs(settings) == {"days": 90}


@pytest.mark.unit
def test_tavily_search_kwargs_maps_time_range_to_days() -> None:
    settings = Settings(TAVILY_SEARCH_DAYS=0, TAVILY_TIME_RANGE="month")
    assert tavily_search_kwargs(settings) == {"days": 30}


@pytest.mark.unit
def test_enhance_search_query_adds_current_year() -> None:
    q = enhance_search_query("Google AI announcements")
    assert "latest" in q.lower() or "2026" in q or "2025" in q


@pytest.mark.unit
def test_enhance_search_query_leaves_explicit_year() -> None:
    q = enhance_search_query("OpenAI latest 2026 product news")
    assert "2026" in q


@pytest.mark.unit
def test_sort_facts_by_recency() -> None:
    old = Fact(
        claim="ChatGPT launched in 2022",
        evidence="In 2022 OpenAI launched ChatGPT",
        source_id=uuid4(),
        confidence="high",
    )
    new = Fact(
        claim="Google announced Gemini 2.5 in 2026",
        evidence="In March 2026 Google announced Gemini 2.5",
        source_id=uuid4(),
        confidence="medium",
    )
    ordered = sort_facts_by_recency([old, new])
    assert ordered[0].claim.startswith("Google")
