"""Research agent — exercises the search tool, iteration cap, and stop signals.

Uses Pydantic AI's TestModel which automatically calls every available tool
with sample arguments. We're not testing model reasoning here; we're testing
that our tool wiring works: budget guarding, persistence into deps.collected,
and that the agent terminates with a valid `ResearchOutput`.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from pydantic_ai.exceptions import UnexpectedModelBehavior
from pydantic_ai.models.test import TestModel

from app.ai.agents.research import _build_agent
from app.ai.budget import TokenBudget
from app.ai.deps import ResearchDeps
from app.ai.schemas import ResearchOutput, SearchResult
from app.llm.tavily_client import StubTavilyClient


def _fake_session() -> Any:
    """Minimal stand-in for AsyncSession; the research tool only needs .add and .flush."""
    s = MagicMock()
    s.add = MagicMock()
    s.flush = AsyncMock()
    return s


@pytest.mark.unit
async def test_research_agent_terminates_with_structured_output() -> None:
    tavily = StubTavilyClient(
        scripted=[
            SearchResult(
                url="https://alpha.example.com/launch",
                title="alpha launches new product",
                snippet="The alpha team announced a major launch in 2025.",
                score=0.85,
            ),
            SearchResult(
                url="https://low-score.example.com",
                title="unrelated post",
                snippet="something off-topic",
                score=0.2,
            ),
        ]
    )
    deps = ResearchDeps(
        run_id=uuid4(),
        topics=["alpha"],
        tavily=tavily,
        budget=TokenBudget(limit=100_000),
        session=_fake_session(),
    )

    agent = _build_agent()
    with agent.override(model=TestModel()):
        result = await agent.run("Research the topics.", deps=deps)

    assert isinstance(result.output, ResearchOutput)
    # The high-score, topic-matching result must have been persisted.
    assert len(deps.collected) == 1
    assert deps.collected[0].url == "https://alpha.example.com/launch"
    # Iteration counter advanced.
    assert deps.iteration_count >= 1


@pytest.mark.unit
async def test_research_agent_filters_by_score_and_topic() -> None:
    tavily = StubTavilyClient(
        scripted=[
            SearchResult(
                url="https://low.example.com",
                title="low score",
                snippet="alpha",
                score=0.1,
            ),
            SearchResult(
                url="https://offtopic.example.com",
                title="off topic",
                snippet="nothing relevant",
                score=0.9,
            ),
        ]
    )
    deps = ResearchDeps(
        run_id=uuid4(),
        topics=["alpha"],
        tavily=tavily,
        budget=TokenBudget(limit=100_000),
        session=_fake_session(),
    )

    agent = _build_agent()
    with agent.override(model=TestModel()):
        with pytest.raises(UnexpectedModelBehavior):
            await agent.run("Research the topics.", deps=deps)

    # Neither result should pass the (score >= 0.5 AND topic-in-text) filter.
    assert len(deps.collected) == 0
