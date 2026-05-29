"""Per-source fact extraction agent.

One call per source. The LLM sees the source text wrapped in <source> XML
tags (the prompt-injection defence) and produces a list of `Fact` objects.

An `@output_validator` stamps `source_id` from `deps` onto every returned
fact, so the LLM can never invent a citation to another source.
"""

from __future__ import annotations

import logging
import time

from pydantic_ai import Agent, RunContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.budget import TokenBudget
from app.ai.deps import ExtractDeps
from app.ai.fact_filter import filter_facts
from app.ai.models import get_extract_model
from app.ai.prompts import EXTRACT_SYSTEM_PROMPT
from app.ai.schemas import Fact
from app.ai.usage_recorder import record_usage
from app.core.config import get_settings
from app.core.llm_logger import log_llm_call
from app.guardrails.wrapping import wrap_source

log = logging.getLogger(__name__)


def _build_agent() -> Agent[ExtractDeps, list[Fact]]:
    agent: Agent[ExtractDeps, list[Fact]] = Agent(
        model=get_extract_model(),
        deps_type=ExtractDeps,
        output_type=list[Fact],
        system_prompt=EXTRACT_SYSTEM_PROMPT,
        retries=1,
    )

    @agent.output_validator
    async def stamp_source_id(
        ctx: RunContext[ExtractDeps], facts: list[Fact]
    ) -> list[Fact]:
        # Cap fact count and stamp the trusted source_id on every Fact.
        cap = get_settings().MAX_FACTS_PER_SOURCE
        capped = facts[:cap]
        for f in capped:
            f.source_id = ctx.deps.source_id
        return capped

    return agent


async def extract_facts(
    *,
    session: AsyncSession,
    run_id: object,
    source_id: object,
    source_text: str,
    budget: TokenBudget,
) -> list[Fact]:
    """Extract facts from one source. Returns a possibly-empty list."""
    budget.guard()
    max_facts = get_settings().MAX_FACTS_PER_SOURCE
    agent = _build_agent()
    user_prompt = (
        f"Extract at most {max_facts} facts from this source.\n\n"
        + wrap_source(source_id, source_text)
    )
    start = time.monotonic()
    result = await agent.run(
        user_prompt,
        deps=ExtractDeps(source_id=source_id, budget=budget),  # type: ignore[arg-type]
    )
    duration_ms = int((time.monotonic() - start) * 1000)
    counts = await record_usage(
        session,
        run_id=run_id,  # type: ignore[arg-type]
        phase="extract",
        usage=result.usage(),
        duration_ms=duration_ms,
    )
    log_llm_call(run_id=run_id, phase="extract", result=result, duration_ms=duration_ms)  # type: ignore[arg-type]
    budget.record(counts.input_tokens, counts.output_tokens)
    return filter_facts(result.output)
