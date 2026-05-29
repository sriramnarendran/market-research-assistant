"""Topic coverage: guarantee searches, ensure gap-fill, topic-aware extract selection."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.ai.agents.research import _guarantee_topic_sources
from app.ai.budget import TokenBudget
from app.ai.deps import ResearchDeps
from app.ai.limits import select_sources_for_extract
from app.ai.schemas import SearchResult
from app.llm.tavily_client import StubTavilyClient


def _fake_session() -> AsyncMock:
    s = AsyncMock()
    s.add = MagicMock()
    s.flush = AsyncMock()
    s.commit = AsyncMock()
    return s


@pytest.mark.unit
async def test_bootstrap_retries_until_topic_covered() -> None:
    calls: list[str] = []

    class RecordingTavily(StubTavilyClient):
        async def search(self, *, query: str, **kwargs):  # type: ignore[no-untyped-def]
            calls.append(query)
            q = query.lower()
            if "aws" in q or "amzn" in q or "amazon" in q:
                return [
                    SearchResult(
                        url="https://aws.amazon.com/news",
                        title="Industry roundup",
                        snippet="Tech giants invest in AI infrastructure.",
                        score=0.92,
                    )
                ]
            if "google" in q:
                return [
                    SearchResult(
                        url="https://blog.google/products/news/",
                        title="Google cloud AI overview",
                        snippet="Google cloud and AI trends across the sector.",
                        score=0.9,
                    )
                ]
            if "microsoft" in q or "azure" in q or "msft" in q:
                return [
                    SearchResult(
                        url="https://blogs.microsoft.com/blog/2026-update",
                        title="Microsoft enterprise cloud roundup",
                        snippet="Microsoft cloud vendors compete on AI infrastructure.",
                        score=0.9,
                    )
                ]
            return []

    deps = ResearchDeps(
        run_id=uuid4(),
        topics=["google", "microsoft", "amazon"],
        tavily=RecordingTavily(scripted=[]),
        budget=TokenBudget(limit=100_000),
        session=_fake_session(),
    )
    await _guarantee_topic_sources(deps)

    assert deps.topics_with_sources == {"google", "microsoft", "amazon"}
    assert len(deps.collected) == 3


@pytest.mark.unit
async def test_dedicated_search_accepts_primary_domain_without_body_match() -> None:
    deps = ResearchDeps(
        run_id=uuid4(),
        topics=["nvidia"],
        tavily=StubTavilyClient(
            scripted=[
                SearchResult(
                    url="https://nvidianews.nvidia.com/news/gtc-2026",
                    title="Weekly tech digest",
                    snippet="Cloud vendors compete on AI agents and chips.",
                    score=0.88,
                )
            ]
        ),
        budget=TokenBudget(limit=100_000),
        session=_fake_session(),
    )
    await _guarantee_topic_sources(deps)

    assert deps.topics_with_sources == {"nvidia"}
    assert deps.collected[0].topic_match == "nvidia"
    assert "nvidia.com" in deps.collected[0].url


@pytest.mark.unit
def test_extract_reserves_one_source_per_topic() -> None:
    g, m, a = uuid4(), uuid4(), uuid4()
    low, mid, high = uuid4(), uuid4(), uuid4()
    research = [(g, "g"), (m, "m"), (a, "a"), (low, "x"), (mid, "y"), (high, "z")]
    scores = {g: 0.7, m: 0.75, a: 0.4, low: 0.1, mid: 0.5, high: 0.99}
    topics = {g: "google", m: "microsoft", a: "amazon", low: "google", mid: "microsoft", high: "google"}

    selected, dropped = select_sources_for_extract(
        [],
        research,
        limit=4,
        research_scores=scores,
        research_topics=topics,
        required_topics=["google", "microsoft", "amazon"],
    )

    selected_ids = {p[0] for p in selected}
    assert {g, m, a}.issubset(selected_ids)
    assert dropped == 2
