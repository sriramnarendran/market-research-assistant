"""Judge DB serialization — prevents concurrent AsyncSession use."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.ai.agents.judge import judge_report
from app.ai.budget import TokenBudget
from app.ai.schemas import Insight, Report


@pytest.mark.unit
async def test_judge_serializes_session_commits() -> None:
    """Concurrent judge tasks must not commit() the same session in parallel."""
    report = Report(
        key_findings=[
            Insight(statement="First claim from sources", citations=[uuid4()]),
            Insight(statement="Second claim from sources", citations=[uuid4()]),
        ],
        topics=["x"],
        source_count=1,
        generated_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
    )
    session = AsyncMock()
    session.execute = AsyncMock()
    in_commit = False

    async def commit() -> None:
        nonlocal in_commit
        if in_commit:
            raise RuntimeError("This transaction is closed")
        in_commit = True
        await asyncio.sleep(0.02)
        in_commit = False

    session.commit = AsyncMock(side_effect=commit)

    verdicts = iter(["verified", "verified"])

    async def fake_run(_prompt, deps=None):
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
        patch("app.ai.agents.judge.get_settings") as settings,
    ):
        load.return_value = {}
        record.return_value = type("C", (), {"input_tokens": 1, "output_tokens": 1})()
        settings.return_value = type("S", (), {"JUDGE_CONCURRENCY": 4})()

        await judge_report(
            session=session,
            run_id=uuid4(),
            report=report,
            budget=TokenBudget(limit=100_000),
        )

    assert session.commit.await_count == 2
