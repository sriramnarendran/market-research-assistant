"""Recency helpers — keep research focused on current market developments."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any, Literal

from app.ai.schemas import Fact

TavilyTimeRange = Literal["day", "week", "month", "year"]

_YEAR_RE = re.compile(r"\b(20\d{2})\b")
_RECENCY_WORDS = frozenset(
    {"latest", "recent", "recently", "current", "today", "new", "news", "update", "updates"}
)


def current_date_utc() -> datetime:
    return datetime.now(UTC)


def research_year_window() -> tuple[int, int]:
    """Inclusive year range we treat as 'current' for market research."""
    year = current_date_utc().year
    return year - 1, year


_TIME_RANGE_DAYS: dict[TavilyTimeRange, int] = {
    "day": 1,
    "week": 7,
    "month": 30,
    "year": 365,
}


def tavily_search_kwargs(settings: Any) -> dict[str, int]:
    """Build Tavily recency kwargs.

    Tavily rejects mixing ``days`` with ``start_date``/``end_date``. The SDK
    always sends ``days`` (default 7), so we use ``days`` only.
    """
    if settings.TAVILY_SEARCH_DAYS > 0:
        return {"days": settings.TAVILY_SEARCH_DAYS}
    if settings.TAVILY_TIME_RANGE:
        return {"days": _TIME_RANGE_DAYS[settings.TAVILY_TIME_RANGE]}
    return {}


def recency_context_block() -> str:
    """Injected into research/synth user prompts so models know 'today'."""
    from app.core.config import get_settings

    settings = get_settings()
    now = current_date_utc()
    y_min, y_max = research_year_window()
    window = (
        f"the last {settings.TAVILY_SEARCH_DAYS} days"
        if settings.TAVILY_SEARCH_DAYS > 0
        else f"{y_min}–{y_max}"
    )
    return (
        f"RESEARCH_DATE: {now.date().isoformat()} (UTC)\n"
        f"RECENCY_POLICY: This is a current-market scan limited to sources from "
        f"{window}. Prioritize the newest facts in that window. Avoid leading with "
        f"historical milestones (e.g. 2022 or earlier) unless they are the only "
        f"relevant facts in the inputs and the user explicitly asked for history.\n\n"
    )


def enhance_search_query(query: str) -> str:
    """Bias Tavily queries toward fresh results when the model omits recency."""
    q = query.strip()
    if not q:
        return q
    lower = q.lower()
    y_min, y_max = research_year_window()
    has_year = any(str(y) in q for y in range(y_min - 2, y_max + 2))
    has_recency_word = any(w in lower for w in _RECENCY_WORDS)
    if has_year and has_recency_word:
        return q
    if has_year:
        return f"{q} latest news"
    return f"{q} latest {y_max}"


def fact_recency_score(fact: Fact) -> int:
    """Highest 4-digit year mentioned in claim/evidence (0 if none)."""
    text = f"{fact.claim} {fact.evidence or ''}"
    years = [int(m.group(1)) for m in _YEAR_RE.finditer(text)]
    return max(years) if years else 0


def sort_facts_by_recency(facts: list[Fact]) -> list[Fact]:
    """Newest-mentioned facts first so synthesis sees recent signal first."""
    return sorted(
        facts,
        key=lambda f: (fact_recency_score(f), f.confidence == "high"),
        reverse=True,
    )
