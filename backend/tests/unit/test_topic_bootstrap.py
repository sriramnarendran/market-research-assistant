"""Bootstrap search ensures each user keyword gets a dedicated query."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.ai.agents.research import _guarantee_topic_sources
from app.ai.budget import TokenBudget
from app.ai.deps import ResearchDeps
from app.ai.schemas import SearchResult
from app.llm.tavily_client import StubTavilyClient


def _fake_session() -> AsyncMock:
    s = AsyncMock()
    s.add = MagicMock()
    s.flush = AsyncMock()
    s.commit = AsyncMock()
    return s


@pytest.mark.unit
async def test_bootstrap_searches_each_uncovered_topic() -> None:
    calls: list[str] = []

    class RecordingTavily(StubTavilyClient):
        async def search(self, *, query: str, **kwargs):  # type: ignore[no-untyped-def]
            calls.append(query)
            topic = next(t for t in ["google", "microsoft", "amazon"] if t in query.lower())
            return [
                SearchResult(
                    url=f"https://example.com/{topic}",
                    title=f"{topic} latest product news",
                    snippet=f"{topic} announced a major update in 2026.",
                    score=0.9,
                )
            ]

    deps = ResearchDeps(
        run_id=uuid4(),
        topics=["google", "microsoft", "amazon"],
        tavily=RecordingTavily(scripted=[]),
        budget=TokenBudget(limit=100_000),
        session=_fake_session(),
    )
    await _guarantee_topic_sources(deps)

    assert len(calls) >= 3
    assert deps.topics_with_sources == {"google", "microsoft", "amazon"}
    assert len(deps.collected) == 3
