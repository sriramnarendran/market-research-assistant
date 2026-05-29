"""Pipeline orchestrator — runs the full research workflow for one `runs` row.

State machine driver. Each transition writes a `run_events` row so failures
are debuggable from the database alone. The function never raises into the
caller; it always leaves the run in a terminal state.

"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.agents.extract import extract_facts
from app.ai.agents.judge import judge_report
from app.ai.agents.research import run_research_topics_parallel
from app.ai.agents.synth import synthesize_report
from app.ai.budget import TokenBudget, TokenBudgetExceeded
from app.ai.diff import apply_change_detection, claim_hash, load_prior_hashes
from app.ai.limits import (
    remaining_extract_slots_by_topic,
    select_sources_for_extract,
)
from app.ai.topic_match import canonical_topic, topic_for_text, uncovered_topics
from app.ai.recency import sort_facts_by_recency
from app.ai.fetch import FetchError, FetchedSource, fetch_http_client, fetch_url
from app.ai.schemas import CollectedSource, Fact, Insight, Report
from app.core.config import get_settings
from app.core.llm_logger import setup_llm_logger
from app.db.models import Run, RunEvent, RunFact, Source
from app.db.session import get_session_factory
from app.llm.tavily_client import get_tavily_client

log = logging.getLogger(__name__)

# A callable producing a fresh AsyncSession context-manager — each concurrent
# task opens its own session because SQLAlchemy AsyncSession is not safe for
# concurrent use from multiple tasks.
SessionFactory = Callable[[], Any]


async def run_pipeline(run_id: UUID) -> None:
    """Entry point for the BackgroundTasks worker.

    Opens its own session (we're outside the request lifecycle) and drives
    the run through the state machine. Always finishes in a terminal state.
    """
    setup_llm_logger()  # idempotent — guarantees the file handler exists
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            await _run(session, session_factory, run_id)
        except Exception as e:  # noqa: BLE001 — last-resort safety net
            log.exception("pipeline crashed for run %s", run_id)
            await _fail(session, run_id, "failed_unknown", str(e))


# -----------------------------------------------------------------------------
# Top-level driver
# -----------------------------------------------------------------------------


async def _run(
    session: AsyncSession, session_factory: SessionFactory, run_id: UUID
) -> None:
    run = await _load_run(session, run_id)
    if run is None:
        log.error("run %s not found", run_id)
        return

    settings = get_settings()
    judge_reserve = min(
        settings.JUDGE_BUDGET_RESERVE,
        settings.PER_RUN_TOKEN_BUDGET // 4,
        max(0, settings.PER_RUN_TOKEN_BUDGET - 20_000),
    )
    budget = TokenBudget(
        limit=settings.PER_RUN_TOKEN_BUDGET,
        judge_reserve=judge_reserve,
    )

    # ---------- fetch (parallel) ----------
    await _transition(session, run, "fetching", detail=f"urls={len(run.urls)}")
    url_sources: list[Source] = []
    fetch_failures: list[tuple[str, str]] = []
    if run.urls:
        url_sources, fetch_failures = await _fetch_and_persist_user_urls(
            session,
            run,
            list(run.urls),
            settings.FETCH_CONCURRENCY,
        )

    if run.urls and not url_sources:
        if run.topics:
            await _event(
                session,
                run.id,
                run.status,
                run.status,
                f"All {len(run.urls)} URL(s) failed to fetch; continuing with topic research.",
            )
        else:
            detail = _format_fetch_failures(fetch_failures or [(u, "unknown error") for u in run.urls])
            await _fail(
                session,
                run.id,
                "failed_fetch",
                f"None of your URLs could be fetched. {detail}",
            )
            return
    elif fetch_failures:
        await _event(
            session,
            run.id,
            run.status,
            run.status,
            f"{len(fetch_failures)} of {len(run.urls)} URL(s) could not be fetched; continuing with the rest.",
        )

    # The URL-leg sources are persisted in `session`; we need their IDs visible
    # to the per-task sessions opened inside _extract_many_concurrently.
    if url_sources:
        await session.commit()

    # ---------- extract from URL sources (parallel) ----------
    url_extract_pairs = [(s.id, s.fetched_text) for s in url_sources]
    url_extract_count = 0
    await _transition(
        session,
        run,
        "extracting",
        detail=f"url_sources={len(url_extract_pairs)}",
    )
    all_facts: list[Fact] = []
    topics_list = list(run.topics or [])
    url_topics_map = {s.id: s.topic_match for s in url_sources}
    if url_extract_pairs:
        url_extract_pairs, url_dropped = select_sources_for_extract(
            url_extract_pairs,
            [],
            limit=settings.MAX_EXTRACT_SOURCES,
            url_topics=url_topics_map,
            required_topics=topics_list if topics_list else None,
        )
        if url_dropped:
            await _event(
                session,
                run.id,
                run.status,
                run.status,
                f"extract cap: skipped {url_dropped} URL source(s) "
                f"(MAX_EXTRACT_SOURCES={settings.MAX_EXTRACT_SOURCES})",
            )
        try:
            url_facts, errors = await _extract_many_concurrently(
                session_factory=session_factory,
                run_id=run.id,
                sources=url_extract_pairs,
                budget=budget,
                concurrency=settings.EXTRACT_CONCURRENCY,
            )
        except TokenBudgetExceeded:
            await _fail(session, run.id, "failed_budget", "token budget exhausted during extract")
            return
        for sid, exc in errors:
            log.warning("extract failed for source %s: %s", sid, exc)
            await _event(
                session, run.id, run.status, run.status,
                f"extract failed for {sid}: {exc}",
            )
        all_facts.extend(url_facts)
        url_extract_count = len(url_extract_pairs)

    url_used_by_topic: dict[str, int] = {}
    for sid, _ in url_extract_pairs:
        topic = url_topics_map.get(sid)
        if topic:
            key = topic.lower()
            url_used_by_topic[key] = url_used_by_topic.get(key, 0) + 1

    research_extract_slots = (
        remaining_extract_slots_by_topic(
            topics=topics_list,
            total_limit=settings.MAX_EXTRACT_SOURCES,
            used_by_topic=url_used_by_topic,
        )
        if topics_list
        else max(0, settings.MAX_EXTRACT_SOURCES - url_extract_count)
    )

    # ---------- research (topic path) ----------
    research_sources_count = 0
    if run.topics:
        await _transition(session, run, "researching", detail=f"topics={len(run.topics)}")
        try:
            research_facts, research_sources_count = await _research_phase(
                session=session,
                session_factory=session_factory,
                run_id=run.id,
                topics=list(run.topics),
                budget=budget,
                settings=settings,
                extract_limit=research_extract_slots,
            )
            all_facts.extend(research_facts)
        except TokenBudgetExceeded:
            await _fail(session, run.id, "failed_budget", "token budget exhausted during research")
            return
        except Exception as e:  # noqa: BLE001
            log.warning("research phase failed: %s", e)
            await _event(session, run.id, run.status, run.status, f"research soft-failed: {e}")
            if not all_facts:
                await _fail(session, run.id, "failed_agent", str(e))
                return

    if not all_facts:
        await _fail(session, run.id, "failed_synth", "no facts produced; nothing to synthesize")
        return

    # ---------- synthesize ----------
    await _transition(session, run, "synthesizing", detail=f"facts={len(all_facts)}")
    all_facts = sort_facts_by_recency(all_facts)
    try:
        report = await synthesize_report(
            session=session,
            run_id=run.id,
            facts=all_facts,
            topics=list(run.topics),
            source_count=len(url_sources) + research_sources_count,
            budget=budget,
        )
    except TokenBudgetExceeded:
        await _fail(session, run.id, "failed_budget", "token budget exhausted during synth")
        return
    except Exception as e:  # noqa: BLE001
        await _fail(session, run.id, "failed_synth", str(e))
        return

    # ---------- judge ----------
    run.report = report.model_dump(mode="json")
    await _transition(session, run, "judging")
    try:
        report = await judge_report(
            session=session,
            run_id=run.id,
            report=report,
            budget=budget,
        )
    except Exception as e:  # noqa: BLE001
        # Judge errors are non-fatal; surface a warning but keep the report.
        log.warning("judge soft-failed: %s", e)
        await _event(session, run.id, run.status, run.status, f"judge soft-failed: {e}")

    # ---------- change detection ----------
    if run.prior_run_id is not None:
        prior_map = await load_prior_hashes(session, run.prior_run_id)
        if prior_map:
            report = apply_change_detection(report, prior_map)

    # ---------- persist run_facts + finalize ----------
    await _persist_run_facts(session, run.id, report)
    has_warnings = _has_unverified_insights(report)
    final_status = "done_with_warnings" if has_warnings else "done"
    run.report = report.model_dump(mode="json")
    run.completed_at = datetime.now(UTC)
    await _transition(session, run, final_status)
    await session.commit()


# -----------------------------------------------------------------------------
# Research phase helper
# -----------------------------------------------------------------------------


async def _research_phase(
    *,
    session: AsyncSession,
    session_factory: SessionFactory,
    run_id: UUID,
    topics: list[str],
    budget: TokenBudget,
    settings: Any,
    extract_limit: int,
) -> tuple[list[Fact], int]:
    """Run per-topic research in parallel, hydrate articles, then extract."""
    collected = await run_research_topics_parallel(
        session_factory=session_factory,
        run_id=run_id,
        topics=topics,
        budget=budget,
        tavily=get_tavily_client(),
        concurrency=settings.RESEARCH_CONCURRENCY,
    )
    covered = {c.topic_match for c in collected if c.topic_match}
    missing = uncovered_topics(topics, covered)
    if missing:
        await _event(
            session,
            run_id,
            "researching",
            "researching",
            f"Could not find web sources for: {', '.join(missing)}",
        )
    if not collected:
        return [], 0

    hydrated = await _hydrate_research_sources_concurrently(
        session_factory=session_factory,
        collected=collected,
        concurrency=settings.FETCH_CONCURRENCY,
    )

    research_scores = {c.source_id: c.score for c in collected}
    research_topics = {c.source_id: c.topic_match for c in collected}
    research_pairs, research_dropped = select_sources_for_extract(
        [],
        hydrated,
        limit=extract_limit,
        research_scores=research_scores,
        research_topics=research_topics,
        required_topics=topics,
    )
    if research_dropped:
        await _event(
            session,
            run_id,
            "researching",
            "researching",
            f"extract cap: skipped {research_dropped} research source(s) "
            f"(slots={extract_limit})",
        )

    facts, errors = await _extract_many_concurrently(
        session_factory=session_factory,
        run_id=run_id,
        sources=research_pairs,
        budget=budget,
        concurrency=settings.EXTRACT_CONCURRENCY,
    )
    for sid, exc in errors:
        log.warning("research-source extract failed for %s: %s", sid, exc)
    return facts, len(research_pairs)


# -----------------------------------------------------------------------------
# Concurrency primitives — used by both the URL leg and the research leg.
# Each task opens its own session because SQLAlchemy AsyncSession is not safe
# to share across asyncio tasks. The shared TokenBudget is lock-protected.
# -----------------------------------------------------------------------------


async def _fetch_and_persist_user_urls(
    session: AsyncSession,
    run: Run,
    urls: list[str],
    concurrency: int,
) -> tuple[list[Source], list[tuple[str, str]]]:
    """Fetch user URLs in parallel; persist each source as soon as it completes."""
    url_sources: list[Source] = []
    fetch_failures: list[tuple[str, str]] = []
    if not urls:
        return url_sources, fetch_failures

    limit = max(1, min(concurrency, len(urls)))
    sem = asyncio.Semaphore(limit)
    db_lock = asyncio.Lock()

    async with fetch_http_client() as client:

        async def _one(input_url: str, url_index: int) -> None:
            async with sem:
                try:
                    result = await fetch_url(input_url, client=client)
                except FetchError as e:
                    err = str(e)
                    async with db_lock:
                        fetch_failures.append((input_url, err))
                        await _event(
                            session,
                            run.id,
                            run.status,
                            run.status,
                            f"fetch failed for {input_url}: {err}",
                        )
                        await session.commit()
                    log.warning("fetch failed for %s: %s", input_url, err)
                    return

                topic_match = _topic_for_user_url(
                    topics=list(run.topics or []),
                    url_index=url_index,
                    url_count=len(urls),
                    title=result.title,
                    text=result.cleaned_text,
                )
                src = Source(
                    run_id=run.id,
                    url=result.url,
                    origin="url_path",
                    title=result.title,
                    fetched_text=result.cleaned_text,
                    content_hash=result.content_hash,
                    bytes=result.bytes_fetched,
                    topic_match=topic_match,
                )
                async with db_lock:
                    session.add(src)
                    await session.flush()
                    await session.commit()
                    url_sources.append(src)

        await asyncio.gather(*[_one(u, i) for i, u in enumerate(urls)])

    return url_sources, fetch_failures


def _topic_for_user_url(
    *,
    topics: list[str],
    url_index: int,
    url_count: int,
    title: str | None,
    text: str,
) -> str | None:
    """Infer which user keyword a URL supports (text match, else index pairing)."""
    if not topics:
        return None
    matched = topic_for_text(f"{title or ''}\n{text}", topics)
    if matched:
        return canonical_topic(matched, topics)
    if url_count == len(topics) and url_index < len(topics):
        return topics[url_index]
    return None


async def _fetch_urls_concurrently(
    urls: list[str], concurrency: int
) -> dict[str, FetchedSource | FetchError]:
    """Parallel `fetch_url` for many URLs (no DB persistence)."""
    from app.ai.fetch import fetch_urls_parallel

    return await fetch_urls_parallel(urls, concurrency=concurrency)


async def _extract_many_concurrently(
    *,
    session_factory: SessionFactory,
    run_id: UUID,
    sources: list[tuple[UUID, str]],
    budget: TokenBudget,
    concurrency: int,
) -> tuple[list[Fact], list[tuple[UUID, Exception]]]:
    """Run `extract_facts` for many sources in parallel.

    Each task gets its own AsyncSession + commits its own usage_event. If any
    task raises TokenBudgetExceeded, that exception is re-raised so the
    pipeline can fail the run as `failed_budget`. Other per-source exceptions
    are collected and returned as (source_id, exception) pairs so the caller
    can log run_events for them.
    """
    if not sources:
        return [], []

    sem = asyncio.Semaphore(concurrency)

    async def _one(sid: UUID, text: str) -> tuple[UUID, list[Fact]]:
        async with sem:
            async with session_factory() as ses:
                facts = await extract_facts(
                    session=ses,
                    run_id=run_id,
                    source_id=sid,
                    source_text=text,
                    budget=budget,
                )
                await ses.commit()
                return sid, facts

    raw = await asyncio.gather(
        *[_one(sid, t) for sid, t in sources], return_exceptions=True
    )

    all_facts: list[Fact] = []
    errors: list[tuple[UUID, Exception]] = []
    for (sid, _text), result in zip(sources, raw, strict=True):
        if isinstance(result, TokenBudgetExceeded):
            raise result
        if isinstance(result, BaseException):
            errors.append((sid, result if isinstance(result, Exception) else Exception(str(result))))
            continue
        all_facts.extend(result[1])
    return all_facts, errors


async def _hydrate_research_sources_concurrently(
    *,
    session_factory: SessionFactory,
    collected: list[CollectedSource],
    concurrency: int,
) -> list[tuple[UUID, str]]:
    """For each research-collected URL, fetch the full article and update its
    source row in place. Returns (source_id, text_to_extract) pairs where
    `text_to_extract` is the cleaned article on a successful fetch, or the
    original Tavily snippet on fetch failure.
    """
    sem = asyncio.Semaphore(concurrency)

    async with fetch_http_client() as client:

        async def _one(c: CollectedSource) -> tuple[UUID, str]:
            async with sem:
                try:
                    fetched = await fetch_url(c.url, client=client)
                except FetchError as e:
                    log.info(
                        "research-source full-fetch failed for %s: %s; using snippet",
                        c.url, e,
                    )
                    return c.source_id, c.snippet

                async with session_factory() as ses:
                    await ses.execute(
                        update(Source)
                        .where(Source.id == c.source_id)
                        .values(
                            fetched_text=fetched.cleaned_text,
                            content_hash=fetched.content_hash,
                            bytes=fetched.bytes_fetched,
                            title=fetched.title or None,
                        )
                    )
                    await ses.commit()
                return c.source_id, fetched.cleaned_text

        return list(await asyncio.gather(*[_one(c) for c in collected]))


# -----------------------------------------------------------------------------
# Persistence helpers
# -----------------------------------------------------------------------------


async def _persist_run_facts(session: AsyncSession, run_id: UUID, report: Report) -> None:
    """Persist one `run_facts` row per insight (theme + competitor groupings)."""
    rows: list[RunFact] = []
    for theme in report.themes:
        for ins in theme.insights:
            rows.append(_make_run_fact(run_id, ins, theme=theme.title))
    for ca in report.competitors:
        for ins in ca.insights:
            rows.append(_make_run_fact(run_id, ins, theme=f"competitor:{ca.competitor}"))
    for ins in report.key_findings:
        rows.append(_make_run_fact(run_id, ins, theme="brief:key_findings"))
    if report.market_trends is not None:
        for ins in report.market_trends.insights:
            rows.append(_make_run_fact(run_id, ins, theme="brief:market_trends"))
    if report.consumer_behavior is not None:
        for ins in report.consumer_behavior.insights:
            rows.append(_make_run_fact(run_id, ins, theme="brief:consumer_behavior"))
    for ins in report.opportunities:
        rows.append(_make_run_fact(run_id, ins, theme="brief:opportunities"))
    for ins in report.risks:
        rows.append(_make_run_fact(run_id, ins, theme="brief:risks"))
    if report.competitive_strategic_synthesis is not None:
        syn = report.competitive_strategic_synthesis
        for ins in syn.dynamics:
            rows.append(_make_run_fact(run_id, ins, theme="synthesis:dynamics"))
        for ins in syn.implications:
            rows.append(_make_run_fact(run_id, ins, theme="synthesis:implications"))
    for ins in report.removed_insights:
        rows.append(_make_run_fact(run_id, ins, theme="diff:removed"))
    if not rows:
        return
    session.add_all(rows)
    await session.flush()


def _make_run_fact(run_id: UUID, ins: Insight, *, theme: str) -> RunFact:
    return RunFact(
        run_id=run_id,
        claim_hash=claim_hash(ins.statement),
        claim=ins.statement,
        theme=theme,
        source_id=ins.citations[0] if ins.citations else None,
        judge_verdict=ins.judge_verdict,
        judge_rationale=ins.judge_rationale,
        diff_tag=ins.diff_tag,
    )


def _has_unverified_insights(report: Report) -> bool:
    def _bad(insights: list[Insight]) -> bool:
        return any(i.judge_verdict == "contradicted" for i in insights)

    for theme in report.themes:
        if _bad(theme.insights):
            return True
    for ca in report.competitors:
        if _bad(ca.insights):
            return True
    if _bad(report.key_findings) or _bad(report.opportunities) or _bad(report.risks):
        return True
    for section in (report.market_trends, report.consumer_behavior):
        if section is not None and _bad(section.insights):
            return True
    if report.competitive_strategic_synthesis is not None:
        syn = report.competitive_strategic_synthesis
        if _bad(syn.dynamics) or _bad(syn.implications):
            return True
    return False


# -----------------------------------------------------------------------------
# State transition helpers
# -----------------------------------------------------------------------------


async def _load_run(session: AsyncSession, run_id: UUID) -> Run | None:
    result = await session.execute(select(Run).where(Run.id == run_id))
    return result.scalar_one_or_none()


async def _transition(
    session: AsyncSession,
    run: Run,
    to_state: str,
    *,
    detail: str | None = None,
) -> None:
    from_state = run.status
    run.status = to_state
    await _event(session, run.id, from_state, to_state, detail)
    await session.commit()


async def _event(
    session: AsyncSession,
    run_id: UUID,
    from_state: str | None,
    to_state: str,
    detail: str | None = None,
) -> None:
    session.add(
        RunEvent(
            run_id=run_id,
            from_state=from_state,
            to_state=to_state,
            detail=detail,
        )
    )
    await session.flush()


def _format_fetch_failures(failures: list[tuple[str, str]], *, limit: int = 3) -> str:
    """Human-readable summary of URL fetch failures for run.failure_reason."""
    parts: list[str] = []
    for url, err in failures[:limit]:
        parts.append(f"{url} ({err})")
    extra = len(failures) - limit
    if extra > 0:
        parts.append(f"…and {extra} more")
    return "Issues: " + "; ".join(parts) + ". Check each link uses http/https and is publicly reachable."


async def _fail(
    session: AsyncSession,
    run_id: UUID,
    status: str,
    reason: str,
) -> None:
    """Move the run to a terminal failure status with a populated reason."""
    run = await _load_run(session, run_id)
    if run is None:
        return
    prev = run.status
    run.status = status
    run.failure_reason = reason
    run.completed_at = datetime.now(UTC)
    await _event(session, run.id, prev, status, reason)
    await session.commit()
