"""Judge behaviour when the run token budget is exhausted."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.ai.agents.judge import judge_report
from app.ai.budget import TokenBudget
from app.ai.schemas import Insight, Report, Theme


@pytest.mark.unit
async def test_budget_skip_leaves_verdict_none() -> None:
    """Skipped insights must not be marked unsupported."""
    report = Report(
        themes=[
            Theme(
                title="Market",
                summary="s",
                insights=[
                    Insight(
                        statement="Acme raised funding in 2024",
                        citations=[uuid4()],
                    )
                ],
            )
        ],
        topics=["x"],
        source_count=1,
        generated_at=datetime.now(UTC),
    )
    budget = TokenBudget(limit=100, judge_reserve=0)
    budget.record(input_tokens=100, output_tokens=0)

    session = AsyncMock()
    session.commit = AsyncMock()

    with patch("app.ai.agents.judge._load_sources", new_callable=AsyncMock) as load:
        load.return_value = {}
        out = await judge_report(
            session=session,
            run_id=uuid4(),
            report=report,
            budget=budget,
        )

    ins = out.themes[0].insights[0]
    assert ins.judge_verdict is None
    assert "budget exhausted" in (ins.judge_rationale or "").lower()
