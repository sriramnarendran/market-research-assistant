"""Synth agent — validates that fabricated source_ids trigger ModelRetry.

We use FunctionModel to script the agent so the first attempt returns a
Report containing a citation NOT in the input facts; the second attempt
returns a clean report. The framework should retry the first and accept
the second.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.ai.agents.synth import _build_agent
from app.ai.budget import TokenBudget
from app.ai.deps import SynthDeps
from app.ai.schemas import Insight, Report, Theme


@pytest.mark.unit
async def test_validator_retries_on_fabricated_source_id() -> None:
    real_sid = uuid4()
    fake_sid = uuid4()
    assert real_sid != fake_sid

    deps = SynthDeps(
        run_id=uuid4(),
        valid_source_ids={real_sid},
        topics=["alpha"],
        budget=TokenBudget(limit=100_000),
    )

    attempts = {"n": 0}

    def make_report(use_real: bool) -> Report:
        cid = real_sid if use_real else fake_sid
        return Report(
            headline="Alpha did something interesting recently.",
            executive_summary=(
                "Alpha announced a meaningful change. The change matters because "
                "it shifts the competitive landscape. Customers will need to "
                "adapt. Competitors are watching."
            ),
            key_metrics=[],
            key_findings=[
                Insight(
                    statement="alpha shipped a major change this quarter",
                    citations=[cid],
                )
            ],
            opportunities=[],
            risks=[],
            themes=[
                Theme(
                    title="Theme A",
                    summary="A summary",
                    insights=[
                        Insight(
                            statement="alpha did something interesting recently",
                            citations=[real_sid],
                        )
                    ],
                )
            ],
            competitors=[],
            outlook=None,
            topics=["alpha"],
            source_count=1,
            generated_at=datetime.now(UTC),
        )

    from pydantic_ai.models.function import AgentInfo, FunctionModel
    from pydantic_ai.messages import ModelMessage, ModelResponse, ToolCallPart

    async def scripted(
        messages: list[ModelMessage], _info: AgentInfo
    ) -> ModelResponse:
        attempts["n"] += 1
        # The framework will invoke the "final result" tool to deliver the structured output.
        report = make_report(use_real=(attempts["n"] >= 2))
        return ModelResponse(
            parts=[
                ToolCallPart(
                    tool_name="final_result",
                    args=report.model_dump(mode="json"),
                )
            ]
        )

    agent = _build_agent()
    with agent.override(model=FunctionModel(scripted)):
        result = await agent.run("FACTS: ...", deps=deps)

    assert attempts["n"] >= 2, "validator must have triggered a retry"
    assert result.output.themes[0].insights[0].citations == [real_sid]
