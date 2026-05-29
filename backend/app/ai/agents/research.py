"""Research agent — the agentic topic loop.

A Pydantic AI `Agent` with one tool (`search`) that calls Tavily. The agent
keeps calling `search` until it decides it has enough information, at which
point it produces a structured `ResearchOutput`. Hard caps on iterations and
token budget are enforced from inside the tool by returning a `note` to the
model, plus a `UsageLimits.request_limit` as a hard backstop.

Side effects: every relevant Tavily result is persisted as a `sources` row
via `_persist_source`. The agent's output enumerates the persisted sources
via their `source_id`s.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from collections.abc import Callable
from typing import Any
from uuid import UUID

from pydantic import BaseModel
from pydantic_ai import Agent, ModelRetry, RunContext
from pydantic_ai.usage import UsageLimits

from app.ai.budget import TokenBudgetExceeded
from app.ai.deps import ResearchDeps, SharedResearchState
from app.ai.models import get_agent_model
from app.ai.prompts import RESEARCH_SYSTEM_PROMPT
from app.ai.prompts.sections import build_research_user_prompt
from app.ai.schemas import CollectedSource, ResearchOutput, SearchResult
from app.ai.recency import enhance_search_query
from app.ai.limits import sources_per_topic_cap
from app.ai.coverage_queries import generate_coverage_queries
from app.ai.topic_match import (
    canonical_topic,
    filter_relevant_results,
    is_topic_covered,
    source_primary_for_topic,
    topic_for_result,
    uncovered_topics,
)
from app.ai.usage_recorder import record_usage
from app.core.config import get_settings
from app.core.llm_logger import log_llm_call
from app.db.models import Source

log = logging.getLogger(__name__)

MAX_ITERATIONS = 8
RELEVANCE_SCORE_MIN = 0.5
DEDICATED_SEARCH_SCORE_MIN = 0.25
DEDICATED_SEARCH_LAST_RESORT_MIN = 0.1
# request_limit covers each Claude call (the model picks a tool or stops).
USAGE_LIMITS = UsageLimits(request_limit=MAX_ITERATIONS + 4)


def _cap_topics(deps: ResearchDeps) -> list[str]:
    return deps.all_topics if deps.all_topics else deps.topics


def _iterations_per_topic(topic_count: int) -> int:
    return max(3, MAX_ITERATIONS // max(1, topic_count))


def _usage_limits_for_topic(topic_count: int) -> UsageLimits:
    per = _iterations_per_topic(topic_count)
    return UsageLimits(request_limit=per + 4)


async def _url_already_collected(deps: ResearchDeps, url: str) -> bool:
    if url in {c.url for c in deps.collected}:
        return True
    if deps.shared is None:
        return False
    async with deps.shared.lock:
        return url in deps.shared.seen_urls


async def _reserve_url(deps: ResearchDeps, url: str) -> bool:
    """Return False if this URL was already collected by any parallel task."""
    if await _url_already_collected(deps, url):
        return False
    if deps.shared is not None:
        async with deps.shared.lock:
            if url in deps.shared.seen_urls:
                return False
            deps.shared.seen_urls.add(url)
    return True


class ToolResponse(BaseModel):
    """What the `search` tool returns to the model on every call."""

    results: list[SearchResult]
    note: str | None = None
    iteration: int
    iterations_remaining: int


# -----------------------------------------------------------------------------
# Agent
# -----------------------------------------------------------------------------


def _build_agent() -> Agent[ResearchDeps, ResearchOutput]:
    agent: Agent[ResearchDeps, ResearchOutput] = Agent(
        model=get_agent_model(),
        deps_type=ResearchDeps,
        output_type=ResearchOutput,
        system_prompt=RESEARCH_SYSTEM_PROMPT,
        retries=2,  # headroom for topic-coverage output_validator retries
    )

    @agent.tool
    async def search(  # noqa: D401
        ctx: RunContext[ResearchDeps],
        query: str,
        rationale: str,
    ) -> ToolResponse:
        """Search the web for information about a topic or competitor.

        Arguments:
            query: the search query string.
            rationale: a brief explanation of why this query advances research.
        """
        return await _execute_search(ctx.deps, query=query, rationale=rationale)

    @agent.output_validator
    async def validate_topic_coverage(
        ctx: RunContext[ResearchDeps], output: ResearchOutput
    ) -> ResearchOutput:
        missing = uncovered_topics(ctx.deps.topics, ctx.deps.topics_with_sources)
        max_iter = _iterations_per_topic(len(_cap_topics(ctx.deps)))
        if missing and ctx.deps.iteration_count < max_iter:
            raise ModelRetry(
                "You must collect at least one source for every user keyword "
                f"before finishing. Still missing: {', '.join(missing)}. "
                "Run search queries that include each missing keyword."
            )
        if missing:
            log.warning(
                "research finished with uncovered topics: %s (run=%s)",
                missing,
                ctx.deps.run_id,
            )
        return output

    return agent


# -----------------------------------------------------------------------------
# Public entry point
# -----------------------------------------------------------------------------


async def run_research(deps: ResearchDeps, user_prompt: str) -> tuple[ResearchOutput, list[CollectedSource]]:
    """Run research for a single session (one or more topics on one deps object)."""
    await _guarantee_topic_sources(deps)

    agent = _build_agent()
    deps.budget.guard()
    start = time.monotonic()
    limits = _usage_limits_for_topic(len(_cap_topics(deps)))
    result = await agent.run(user_prompt, deps=deps, usage_limits=limits)
    await _guarantee_topic_sources(deps)
    duration_ms = int((time.monotonic() - start) * 1000)

    counts = await record_usage(
        deps.session,
        run_id=deps.run_id,
        phase="agent",
        usage=result.usage(),
        duration_ms=duration_ms,
    )
    log_llm_call(run_id=deps.run_id, phase="agent", result=result, duration_ms=duration_ms)
    deps.budget.record(counts.input_tokens, counts.output_tokens)
    return result.output, list(deps.collected)


async def run_research_topics_parallel(
    *,
    session_factory: Callable[[], Any],
    run_id: UUID,
    topics: list[str],
    budget: Any,
    tavily: Any,
    concurrency: int,
    enable_agent: bool = True,
) -> list[CollectedSource]:
    """Research each user keyword in parallel (separate DB session per topic)."""
    if not topics:
        return []

    shared = SharedResearchState()
    limit = max(1, min(concurrency, len(topics)))
    sem = asyncio.Semaphore(limit)

    async def _one(topic: str) -> list[CollectedSource]:
        async with sem:
            async with session_factory() as session:
                return await _research_one_topic(
                    session=session,
                    run_id=run_id,
                    topic=topic,
                    all_topics=topics,
                    budget=budget,
                    tavily=tavily,
                    shared=shared,
                    enable_agent=enable_agent,
                )

    batches = await asyncio.gather(*[_one(t) for t in topics])
    merged: list[CollectedSource] = []
    for batch in batches:
        merged.extend(batch)
    return merged


async def _research_one_topic(
    *,
    session: Any,
    run_id: UUID,
    topic: str,
    all_topics: list[str],
    budget: Any,
    tavily: Any,
    shared: SharedResearchState,
    enable_agent: bool,
) -> list[CollectedSource]:
    """Coverage searches + optional agent loop for a single keyword."""
    deps = ResearchDeps(
        run_id=run_id,
        topics=[topic],
        all_topics=all_topics,
        tavily=tavily,
        budget=budget,
        session=session,
        shared=shared,
    )
    await _guarantee_topic_sources(deps)

    if enable_agent:
        agent = _build_agent()
        try:
            budget.guard()
        except TokenBudgetExceeded:
            log.info("skipping agent for topic=%s run=%s: budget exhausted", topic, run_id)
        else:
            prompt = build_research_user_prompt([topic])
            start = time.monotonic()
            limits = _usage_limits_for_topic(len(all_topics))
            result = await agent.run(prompt, deps=deps, usage_limits=limits)
            duration_ms = int((time.monotonic() - start) * 1000)
            counts = await record_usage(
                session,
                run_id=run_id,
                phase="agent",
                usage=result.usage(),
                duration_ms=duration_ms,
            )
            log_llm_call(run_id=run_id, phase="agent", result=result, duration_ms=duration_ms)
            budget.record(counts.input_tokens, counts.output_tokens)

    await _guarantee_topic_sources(deps)
    await session.commit()
    return list(deps.collected)


# -----------------------------------------------------------------------------
# Search execution
# -----------------------------------------------------------------------------


async def _guarantee_topic_sources(deps: ResearchDeps) -> None:
    """Deterministic per-topic searches until every keyword has a source row."""
    for topic in list(deps.topics):
        if is_topic_covered(topic, deps.topics, deps.topics_with_sources):
            continue
        await _search_until_topic_covered(deps, topic=topic, phase="coverage")


def _collection_cap(deps: ResearchDeps) -> int:
    """Total research sources collected — scales with topic count."""
    settings = get_settings()
    n = max(1, len(_cap_topics(deps)))
    return sources_per_topic_cap(
        total_slots=settings.MAX_EXTRACT_SOURCES,
        topic_count=n,
    ) * n


def _max_sources_for_topic(deps: ResearchDeps, topic: str) -> int:
    """Equal per-topic collection ceiling (always allow first source for gap-fill)."""
    n = max(1, len(_cap_topics(deps)))
    return sources_per_topic_cap(
        total_slots=get_settings().MAX_EXTRACT_SOURCES,
        topic_count=n,
    )


def _topic_source_count(deps: ResearchDeps, topic: str) -> int:
    key = canonical_topic(topic, deps.topics).lower()
    return sum(
        1
        for c in deps.collected
        if c.topic_match and c.topic_match.lower() == key
    )


async def _search_until_topic_covered(
    deps: ResearchDeps,
    *,
    topic: str,
    phase: str,
) -> None:
    """Try query variants with progressively looser relevance gates."""
    canonical = canonical_topic(topic, deps.topics)
    queries = await generate_coverage_queries(
        canonical,
        budget=deps.budget,
        run_id=deps.run_id,
        session=deps.session,
    )
    attempts: list[tuple[float, bool]] = [
        (RELEVANCE_SCORE_MIN, True),
        (DEDICATED_SEARCH_SCORE_MIN, True),
        (DEDICATED_SEARCH_LAST_RESORT_MIN, True),
    ]
    for score_min, accept_top in attempts:
        if is_topic_covered(canonical, deps.topics, deps.topics_with_sources):
            return
        for query in queries:
            if is_topic_covered(canonical, deps.topics, deps.topics_with_sources):
                return
            log.info(
                "%s search for topic=%s run=%s query=%r score_min=%s",
                phase,
                canonical,
                deps.run_id,
                query,
                score_min,
            )
            await _execute_search(
                deps,
                query=query,
                rationale=f"{phase}: ensure sources for user keyword {canonical}",
                count_toward_agent_cap=False,
                attributed_topic=canonical,
                accept_top_hit_if_empty=accept_top,
                score_min=score_min,
                commit_after=True,
            )
            if is_topic_covered(canonical, deps.topics, deps.topics_with_sources):
                return

    if not is_topic_covered(canonical, deps.topics, deps.topics_with_sources):
        log.warning(
            "%s could not find sources for topic=%s (run=%s)",
            phase,
            canonical,
            deps.run_id,
        )


async def _execute_search(
    deps: ResearchDeps,
    *,
    query: str,
    rationale: str,
    count_toward_agent_cap: bool = True,
    attributed_topic: str | None = None,
    accept_top_hit_if_empty: bool = False,
    score_min: float = RELEVANCE_SCORE_MIN,
    commit_after: bool = False,
) -> ToolResponse:
    if count_toward_agent_cap:
        deps.iteration_count += 1
    iteration = deps.iteration_count
    max_iter = _iterations_per_topic(len(_cap_topics(deps)))
    remaining = max(0, max_iter - iteration)

    if count_toward_agent_cap and iteration > max_iter:
        return ToolResponse(
            results=[],
            note="Iteration cap reached. Produce final structured output now.",
            iteration=iteration,
            iterations_remaining=0,
        )

    try:
        deps.budget.guard()
    except Exception:
        return ToolResponse(
            results=[],
            note="Token budget exceeded. Produce final structured output now.",
            iteration=iteration,
            iterations_remaining=remaining,
        )

    enhanced_query = enhance_search_query(query)
    try:
        raw = await deps.tavily.search(
            query=enhanced_query,
            max_results=5,
            search_depth="advanced",
        )
    except Exception as e:  # noqa: BLE001
        log.warning("tavily search failed: %s", e)
        return ToolResponse(
            results=[],
            note=f"Search failed: {e}. Try a different query or produce final output.",
            iteration=iteration,
            iterations_remaining=remaining,
        )

    relevant = filter_relevant_results(
        raw,
        deps.topics,
        score_min=score_min,
        query=query,
        attributed_topic=attributed_topic,
        accept_top_hit_if_empty=accept_top_hit_if_empty,
    )
    if not relevant and attributed_topic and raw:
        candidates = [
            r
            for r in raw
            if r.score >= score_min
            and source_primary_for_topic(r, attributed_topic, _cap_topics(deps))
            and not await _url_already_collected(deps, r.url)
        ]
        if candidates:
            relevant = [max(candidates, key=lambda r: r.score)]

    if not relevant:
        missing = uncovered_topics(deps.topics, deps.topics_with_sources)
        gap = (
            f" No sources collected yet for: {', '.join(missing)}."
            if missing
            else ""
        )
        return ToolResponse(
            results=[],
            note=(
                "No relevant results for that query. Include the exact user "
                f"keyword and try a different angle.{gap}"
            ),
            iteration=iteration,
            iterations_remaining=remaining,
        )

    max_sources = _collection_cap(deps)
    added: list[SearchResult] = []
    cap_note: str | None = None

    for r in relevant:
        if not await _reserve_url(deps, r.url):
            continue
        raw_topic = attributed_topic or topic_for_result(r, deps.topics, query=query)
        if not raw_topic:
            continue
        topic = canonical_topic(raw_topic, deps.topics)
        if (
            not attributed_topic
            and not source_primary_for_topic(r, topic, _cap_topics(deps))
        ):
            continue
        gap_fill = not is_topic_covered(topic, deps.topics, deps.topics_with_sources)
        if (
            not gap_fill
            and _topic_source_count(deps, topic) >= _max_sources_for_topic(deps, topic)
        ):
            continue
        if len(deps.collected) >= max_sources and not gap_fill:
            cap_note = (
                f"Source cap ({max_sources}) reached. "
                "Produce final structured output now."
            )
            break

        source_id = await _persist_source(deps, r, topic=topic)
        deps.topics_with_sources.add(topic)
        deps.collected.append(
            CollectedSource(
                source_id=source_id,
                url=r.url,
                title=r.title,
                snippet=r.snippet,
                score=r.score,
                topic_match=topic,
            )
        )
        added.append(r)
        if commit_after:
            await deps.session.commit()

    notes: list[str] = []
    if cap_note:
        notes.append(cap_note)
    missing = uncovered_topics(deps.topics, deps.topics_with_sources)
    if missing and remaining > 0:
        notes.append(
            "Topic coverage incomplete — no sources yet for: "
            f"{', '.join(missing)}. Your next search MUST include one of "
            "those keywords before finishing."
        )
    at_cap = [
        t
        for t in deps.topics
        if _topic_source_count(deps, t) >= _max_sources_for_topic(deps, t)
    ]
    if at_cap and missing:
        notes.append(
            f"Source quota reached for: {', '.join(at_cap)}. "
            "Search for uncovered keywords only."
        )

    return ToolResponse(
        results=added,
        note=" ".join(notes) if notes else None,
        iteration=iteration,
        iterations_remaining=remaining,
    )


async def _persist_source(
    deps: ResearchDeps, r: SearchResult, *, topic: str
) -> UUID:
    """Insert a `sources` row for one Tavily result and return its id."""
    from uuid import uuid4

    body = (r.snippet or "").strip()
    digest = hashlib.sha256(body.encode("utf-8", errors="ignore")).hexdigest()
    source_id = uuid4()
    row = Source(
        id=source_id,
        run_id=deps.run_id,
        url=r.url,
        origin="tavily",
        title=r.title or None,
        fetched_text=body,
        content_hash=digest,
        bytes=len(body.encode("utf-8", errors="ignore")),
        topic_match=topic,
    )
    deps.session.add(row)
    await deps.session.flush()
    return source_id
