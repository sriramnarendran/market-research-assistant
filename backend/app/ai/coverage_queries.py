"""LLM-generated Tavily queries for per-topic coverage bootstrap."""

from __future__ import annotations

import logging
import time
from uuid import UUID

from pydantic import BaseModel, Field
from pydantic_ai import Agent

from app.ai.budget import TokenBudget
from app.ai.models import get_agent_model
from app.ai.recency import recency_context_block
from app.ai.usage_recorder import record_usage
from app.core.llm_logger import log_llm_call
from app.guardrails.wrapping import wrap_topics

log = logging.getLogger(__name__)

COVERAGE_QUERY_SYSTEM_PROMPT = """\
You write web search queries for Tavily to find recent, primary sources about \
one user research keyword.

Output 4–6 diverse queries. Each query MUST help Tavily find authoritative \
pages about that keyword — you supply the entity intelligence; the search \
engine only executes your strings.

Include where useful:
- Official company, product, and brand names
- Common aliases and abbreviations (e.g. AWS for Amazon, MSFT for Microsoft)
- Parent companies and related brands (e.g. Alphabet for Google)
- Ticker symbols for public companies
- `site:` filters for official blogs or newsrooms
- Recency terms (current year, "latest", "announcement", "news")
- Different angles: product launches, earnings, strategy, partnerships

Do NOT output generic industry queries that omit the keyword's entity names.
Do NOT invent facts — only craft search strings.
"""


class CoverageQueriesOutput(BaseModel):
    queries: list[str] = Field(
        ...,
        min_length=1,
        max_length=8,
        description="Tavily search queries, most specific first.",
    )


def _fallback_queries(topic: str) -> list[str]:
    from app.ai.recency import research_year_window

    end_year = research_year_window()[1]
    return [
        f"{topic} latest news announcement {end_year}",
        f"{topic} products strategy news {end_year}",
    ]


def _dedupe_queries(queries: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for q in queries:
        normalized = q.strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            unique.append(normalized)
    return unique


async def generate_coverage_queries(
    topic: str,
    *,
    budget: TokenBudget,
    run_id: UUID | None = None,
    session=None,
) -> list[str]:
    """Ask the LLM for Tavily queries; fall back to simple templates on failure."""
    fallbacks = _fallback_queries(topic)
    budget.guard()

    agent: Agent[None, CoverageQueriesOutput] = Agent(
        model=get_agent_model(),
        output_type=CoverageQueriesOutput,
        system_prompt=COVERAGE_QUERY_SYSTEM_PROMPT,
        retries=1,
    )
    user_prompt = (
        recency_context_block().rstrip()
        + "\n\nResearch keyword:\n"
        + wrap_topics([topic])
        + "\n\nReturn search queries tailored to this keyword."
    )

    try:
        start = time.monotonic()
        result = await agent.run(user_prompt)
        duration_ms = int((time.monotonic() - start) * 1000)
        if session is not None and run_id is not None:
            counts = await record_usage(
                session,
                run_id=run_id,
                phase="coverage_queries",
                usage=result.usage,
                duration_ms=duration_ms,
            )
            budget.record(counts.input_tokens, counts.output_tokens)
            log_llm_call(
                run_id=run_id,
                phase="coverage_queries",
                result=result,
                duration_ms=duration_ms,
            )
        llm_queries = [q.strip() for q in result.output.queries if q.strip()]
    except Exception as exc:  # noqa: BLE001
        log.warning("coverage query generation failed for topic=%s: %s", topic, exc)
        llm_queries = []

    merged = _dedupe_queries(llm_queries + fallbacks)
    return merged[:8]
