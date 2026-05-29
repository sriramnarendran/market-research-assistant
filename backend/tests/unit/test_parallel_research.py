"""Parallel per-topic research."""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.ai.agents.research import run_research_topics_parallel
from app.ai.budget import TokenBudget
from app.ai.schemas import SearchResult
from app.llm.tavily_client import StubTavilyClient


def _fake_session() -> AsyncMock:
    s = AsyncMock()
    s.add = MagicMock()
    s.flush = AsyncMock()
    s.commit = AsyncMock()
    return s


@pytest.mark.unit
async def test_parallel_research_one_task_per_topic() -> None:
    class RecordingTavily(StubTavilyClient):
        async def search(self, *, query: str, **kwargs):  # type: ignore[no-untyped-def]
            q = query.lower()
            if "alpha" in q:
                return [
                    SearchResult(
                        url="https://alpha.example.com/news",
                        title="alpha product launch",
                        snippet="alpha announced a launch in 2026.",
                        score=0.9,
                    )
                ]
            if "beta" in q:
                return [
                    SearchResult(
                        url="https://beta.example.com/news",
                        title="beta platform update",
                        snippet="beta announced a platform update in 2026.",
                        score=0.9,
                    )
                ]
            return []

    sessions: list[AsyncMock] = []

    @asynccontextmanager
    async def factory():
        s = _fake_session()
        sessions.append(s)
        yield s

    collected = await run_research_topics_parallel(
        session_factory=factory,
        run_id=uuid4(),
        topics=["alpha", "beta"],
        budget=TokenBudget(limit=100_000),
        tavily=RecordingTavily(scripted=[]),
        concurrency=2,
        enable_agent=False,
    )

    assert len(sessions) == 2
    assert len(collected) == 2
    assert {c.topic_match for c in collected} == {"alpha", "beta"}
