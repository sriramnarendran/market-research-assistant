"""Phase 1.3b smoke test — proves Pydantic AI is wired correctly against TestModel.

This test does not hit Azure. It only verifies:
  1. `get_*_model()` returns a working `TestModel` in test mode.
  2. An `Agent` with a structured `output_type` returns a validated instance.
  3. The `info_for(phase)` helper returns the `test` provider.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import BaseModel

from app.ai.models import (
    get_agent_model,
    get_extract_model,
    get_judge_model,
    get_synth_model,
    info_for,
)


class _SmokeOutput(BaseModel):
    answer: str
    confidence: float


@pytest.mark.unit
def test_info_for_returns_test_provider_in_test_mode() -> None:
    for phase in ("extract", "synth", "agent", "judge"):
        info = info_for(phase)
        assert info.provider == "test"
        assert info.model == "test"


@pytest.mark.unit
def test_all_factories_return_testmodel_instances() -> None:
    """Phase 1.3b — every factory must return a usable Pydantic AI model.

    We check the class name rather than isinstance to avoid an import-time
    dependency on `pydantic_ai.models.test.TestModel` from this test.
    """
    for factory in (get_agent_model, get_extract_model, get_synth_model, get_judge_model):
        model = factory()
        assert type(model).__name__ == "TestModel"


@pytest.mark.unit
async def test_agent_returns_validated_output_against_test_model() -> None:
    """End-to-end Pydantic AI smoke: agent + structured output_type + run."""
    from pydantic_ai import Agent

    agent: Agent[None, _SmokeOutput] = Agent(
        model=get_agent_model(),
        output_type=_SmokeOutput,
        system_prompt="You are a smoke-test agent.",
    )
    result = await agent.run("Hello")
    assert isinstance(result.output, _SmokeOutput)


@pytest.mark.unit
def test_datetime_import_smoke() -> None:
    # Sanity check that timezone-aware datetimes work; used by Report.generated_at.
    assert datetime.now(UTC).tzinfo is not None
