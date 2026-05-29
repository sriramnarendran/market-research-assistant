"""Extract agent — exercises the output_validator that stamps source_id."""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic_ai.models.test import TestModel

from app.ai.agents.extract import _build_agent
from app.ai.budget import TokenBudget
from app.ai.deps import ExtractDeps
from app.ai.schemas import Fact


@pytest.mark.unit
async def test_extract_stamps_source_id_from_deps() -> None:
    """The LLM never sees the real source_id; the validator must stamp it."""
    sid = uuid4()
    agent = _build_agent()

    facts_template = [
        Fact(
            claim="alpha launched a new product",
            evidence="alpha announced the launch on its blog",
            confidence="high",
        ),
        Fact(
            claim="alpha raised a Series B",
            evidence="press release dated 2025-02-01",
            confidence="medium",
        ),
    ]

    with agent.override(model=TestModel(custom_output_args=facts_template)):
        result = await agent.run(
            "<source id='ignored'>article body</source>",
            deps=ExtractDeps(source_id=sid, budget=TokenBudget(limit=100_000)),
        )

    assert len(result.output) == 2
    for f in result.output:
        assert f.source_id == sid
