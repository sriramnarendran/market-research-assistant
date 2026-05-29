"""Unit tests for incremental judge report snapshots."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.ai.agents.judge import _persist_report_snapshot, iter_report_insights
from app.ai.schemas import Insight, Report, Theme


@pytest.mark.unit
async def test_persist_report_snapshot_updates_run() -> None:
    run_id = uuid4()
    report = Report(
        key_findings=[Insight(statement="Acme shipped a feature", citations=[uuid4()])],
        topics=["acme"],
        source_count=1,
        generated_at=datetime.now(UTC),
    )
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()

    await _persist_report_snapshot(session, run_id, report)

    session.execute.assert_awaited_once()
    session.commit.assert_awaited_once()


@pytest.mark.unit
def test_iter_report_insights_order() -> None:
    finding = Insight(statement="First finding insight", citations=[uuid4()])
    theme_ins = Insight(statement="Theme insight detail", citations=[uuid4()])
    report = Report(
        key_findings=[finding],
        themes=[Theme(title="Theme A", summary="Summary text", insights=[theme_ins])],
        topics=["x"],
        source_count=1,
        generated_at=datetime.now(UTC),
    )
    ordered = iter_report_insights(report)
    assert ordered[0] is finding
    assert ordered[1] is theme_ins


@pytest.mark.unit
async def test_judge_persists_after_each_insight() -> None:
    report = Report(
        key_findings=[
            Insight(statement="First claim from sources", citations=[uuid4()]),
            Insight(statement="Second claim from sources", citations=[uuid4()]),
        ],
        topics=["x"],
        source_count=1,
        generated_at=datetime.now(UTC),
    )
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()

    verdicts = iter(["verified", "unsupported"])

    async def fake_run(_prompt, deps=None):
        from pydantic_ai.messages import ModelResponse
        from pydantic_ai.models.function import AgentInfo

        class FakeResult:
            def usage(self):
                class U:
                    input_tokens = 10
                    output_tokens = 5

                return U()

            output = type("V", (), {"verdict": next(verdicts), "rationale": "ok"})()

        return FakeResult()

    agent = MagicMock()
    agent.run = AsyncMock(side_effect=fake_run)

    with (
        patch("app.ai.agents.judge._build_agent", return_value=agent),
        patch("app.ai.agents.judge._load_sources", new_callable=AsyncMock) as load,
        patch("app.ai.agents.judge.record_usage", new_callable=AsyncMock) as record,
        patch("app.ai.agents.judge.log_llm_call"),
    ):
        load.return_value = {}
        record.return_value = type("C", (), {"input_tokens": 1, "output_tokens": 1})()

        from app.ai.agents.judge import judge_report
        from app.ai.budget import TokenBudget

        await judge_report(
            session=session,
            run_id=uuid4(),
            report=report,
            budget=TokenBudget(limit=100_000),
        )

    assert session.commit.await_count == 2
