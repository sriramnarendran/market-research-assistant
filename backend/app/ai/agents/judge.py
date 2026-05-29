"""LLM-as-judge agent.

Runs on a DIFFERENT model family from the rest of the pipeline (Azure OpenAI
GPT-5 mini, while extract/synth/agent use Azure Foundry Claude Sonnet). This
gives the judgement statistical independence — the same model rarely catches
its own subtle mistakes.

Per-insight workflow:
  1. Look up the insight's cited source rows and prepare excerpts.
  2. Run the judge agent against insight + excerpts.
  3. Stamp the verdict + rationale onto the insight.

Insights flagged as `unsupported` or `contradicted` are NOT dropped — the UI
displays them with a warning badge. Runs are marked `done_with_warnings` only
when at least one insight is `contradicted`.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any
from uuid import UUID

from pydantic_ai import Agent
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.budget import TokenBudget, TokenBudgetExceeded
from app.ai.deps import JudgeDeps
from app.ai.models import get_judge_model
from app.ai.prompts import JUDGE_SYSTEM_PROMPT
from app.ai.schemas import Insight, JudgeVerdict, Report
from app.ai.usage_recorder import record_usage
from app.core.config import get_settings
from app.core.llm_logger import log_llm_call
from app.db.models import Run, Source
from app.guardrails.wrapping import wrap_excerpt

log = logging.getLogger(__name__)

# Cap on excerpt length per source. At ~4 chars/token this is ~5K tokens, well
# under GPT-5 mini's context window. Set generously so most blog-length articles
# fit in their entirety — the judge needs the surrounding context to verify
# specific claims (numbers, named entities, quoted phrases).
EXCERPT_MAX_CHARS = 20_000
# Conservative estimate for one judge call (system + insight + excerpts + output).
ESTIMATED_TOKENS_PER_JUDGE_CALL = 3_500


def _build_agent() -> Agent[JudgeDeps, JudgeVerdict]:
    return Agent(
        model=get_judge_model(),
        deps_type=JudgeDeps,
        output_type=JudgeVerdict,
        system_prompt=JUDGE_SYSTEM_PROMPT,
        retries=2,
    )


def iter_report_insights(report: Report) -> list[Insight]:
    """Every insight the judge annotates, in display-priority order."""
    insights: list[Insight] = []
    insights.extend(report.key_findings)
    for section in (report.market_trends, report.consumer_behavior):
        if section is not None:
            insights.extend(section.insights)
    insights.extend(report.opportunities)
    insights.extend(report.risks)
    if report.competitive_strategic_synthesis is not None:
        syn = report.competitive_strategic_synthesis
        insights.extend(syn.dynamics)
        insights.extend(syn.implications)
    for theme in report.themes:
        insights.extend(theme.insights)
    for ca in report.competitors:
        insights.extend(ca.insights)
    return insights


async def _persist_report_snapshot(
    session: AsyncSession,
    run_id: UUID,
    report: Report,
) -> None:
    """Write the in-progress report so clients can poll verdict updates."""
    await session.execute(
        update(Run)
        .where(Run.id == run_id)
        .values(report=report.model_dump(mode="json"))
    )
    await session.commit()


async def _persist_judge_progress(
    session: AsyncSession,
    *,
    run_id: UUID,
    report: Report,
    budget: TokenBudget,
    usage: Any | None = None,
    duration_ms: int = 0,
) -> None:
    """Record usage (optional) and snapshot the report — must run serially on *session*."""
    if usage is not None:
        counts = await record_usage(
            session,
            run_id=run_id,
            phase="judge",
            usage=usage,
            duration_ms=duration_ms,
        )
        budget.record(counts.input_tokens, counts.output_tokens)
    await session.execute(
        update(Run)
        .where(Run.id == run_id)
        .values(report=report.model_dump(mode="json"))
    )
    await session.commit()


async def judge_report(
    *,
    session: AsyncSession,
    run_id: UUID,
    report: Report,
    budget: TokenBudget,
) -> Report:
    """Annotate every insight in the report with a judge verdict + rationale.

    Mutates `report` in place and also returns it for chaining. If the token
    budget runs out mid-judge, remaining insights keep `judge_verdict=None`
    with a rationale explaining the skip (not flagged as unsupported).
    """
    agent = _build_agent()

    all_insights = iter_report_insights(report)

    if not all_insights:
        return report

    # Preload source rows once so we don't N+1 the DB during judging.
    cited_ids: set[UUID] = set()
    for ins in all_insights:
        cited_ids.update(ins.citations)
    src_by_id = await _load_sources(session, cited_ids)

    settings = get_settings()
    excerpt_max = _excerpt_max_chars(budget, insight_count=len(all_insights))
    remaining = budget.remaining(for_judge=True)
    affordable = max(1, remaining // ESTIMATED_TOKENS_PER_JUDGE_CALL)
    concurrency = min(settings.JUDGE_CONCURRENCY, affordable)
    if affordable < len(all_insights):
        log.warning(
            "judge budget fits ~%d of %d insights (remaining=%d tokens); "
            "later insights may be skipped",
            affordable,
            len(all_insights),
            remaining,
        )
    log.info(
        "judge phase start",
        extra={
            "run_id": str(run_id),
            "insights": len(all_insights),
            "remaining_tokens": remaining,
            "excerpt_max_chars": excerpt_max,
            "concurrency": concurrency,
        },
    )
    sem = asyncio.Semaphore(concurrency)
    # AsyncSession is not concurrent-safe; one task's commit() was closing the
    # transaction while others still called record_usage() → "transaction is closed".
    db_lock = asyncio.Lock()

    async def _snapshot_progress(
        *,
        usage: Any | None = None,
        duration_ms: int = 0,
    ) -> None:
        async with db_lock:
            await _persist_judge_progress(
                session,
                run_id=run_id,
                report=report,
                budget=budget,
                usage=usage,
                duration_ms=duration_ms,
            )

    async def _judge_one(ins: Insight) -> None:
        async with sem:
            if budget.remaining(for_judge=True) < ESTIMATED_TOKENS_PER_JUDGE_CALL:
                ins.judge_verdict = None
                ins.judge_rationale = "Judge skipped: run token budget exhausted."
                await _snapshot_progress()
                return
            try:
                budget.guard(for_judge=True)
            except TokenBudgetExceeded:
                ins.judge_verdict = None
                ins.judge_rationale = "Judge skipped: run token budget exhausted."
                await _snapshot_progress()
                return

            excerpts_block = _build_excerpts_block(
                ins, src_by_id, max_chars=excerpt_max
            )
            user_prompt = (
                f"INSIGHT: {ins.statement}\n\n"
                f"EXCERPTS:\n{excerpts_block}"
            )
            deps = JudgeDeps(run_id=run_id, budget=budget)
            try:
                budget.guard(for_judge=True)
                start = time.monotonic()
                result = await agent.run(user_prompt, deps=deps)
                duration_ms = int((time.monotonic() - start) * 1000)

                verdict = result.output
                ins.judge_verdict = verdict.verdict
                ins.judge_rationale = verdict.rationale
                await _snapshot_progress(usage=result.usage(), duration_ms=duration_ms)
                log_llm_call(
                    run_id=run_id,
                    phase="judge",
                    result=result,
                    duration_ms=duration_ms,
                )
            except Exception as e:  # noqa: BLE001
                log.warning("judge failed for insight: %s", e)
                ins.judge_verdict = None
                ins.judge_rationale = "Citation check could not be completed."
                await _snapshot_progress()

    await asyncio.gather(*[_judge_one(ins) for ins in all_insights])

    return report


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------


async def _load_sources(session: AsyncSession, ids: set[UUID]) -> dict[UUID, Source]:
    if not ids:
        return {}
    result = await session.execute(select(Source).where(Source.id.in_(ids)))
    return {s.id: s for s in result.scalars().all()}


def _excerpt_max_chars(budget: TokenBudget, *, insight_count: int) -> int:
    """Size excerpts so many insights can share the remaining judge budget.

    Previously we used 20k chars whenever >80k tokens remained, which caused
    ~36 parallel judge calls to blow past a 200k run cap even when a reserve
    was configured.
    """
    remaining = budget.remaining(for_judge=True)
    if insight_count <= 0:
        return EXCERPT_MAX_CHARS
    tokens_per_insight = (remaining * 0.85) / insight_count
    chars = int(tokens_per_insight * 4 * 0.65)
    if remaining > 80_000 and insight_count <= 8:
        return min(EXCERPT_MAX_CHARS, max(4_000, chars))
    return max(2_000, min(EXCERPT_MAX_CHARS, chars))


def _build_excerpts_block(
    insight: Insight,
    src_by_id: dict[UUID, Source],
    *,
    max_chars: int,
) -> str:
    """Compose the <excerpt> block fed to the judge for one insight."""
    pieces: list[str] = []
    for cid in insight.citations:
        src = src_by_id.get(cid)
        if src is None:
            pieces.append(wrap_excerpt(cid, "[source missing]"))
            continue
        text = src.fetched_text or ""
        window = _select_window(text, insight.statement, max_chars=max_chars)
        pieces.append(wrap_excerpt(cid, window))
    return "\n\n".join(pieces)


def _select_window(text: str, statement: str, *, max_chars: int = EXCERPT_MAX_CHARS) -> str:
    """Pick a windowed substring of `text` likely to be the relevant excerpt.

    When the source fits inside `EXCERPT_MAX_CHARS` we return it whole — the
    judge gets the full article and can find evidence anywhere in it.

    When the source is larger, we score every keyword occurrence by how many
    OTHER keyword occurrences fall inside a centred window of the same size,
    and pick the densest cluster. This beats "first match" because a single
    early occurrence of a common word ("anthropic", "model") will otherwise
    pin the window to the intro and miss the section that actually backs
    the insight.
    """
    if not text:
        return ""
    if len(text) <= max_chars:
        return text

    keywords = _extract_keywords(statement)
    haystack = text.lower()
    positions = sorted({p for kw in keywords for p in _find_all(haystack, kw)})
    if not positions:
        return text[:max_chars]

    half = max_chars // 2
    best_center = positions[0]
    best_count = -1
    for center in positions:
        lo, hi = center - half, center + half
        # positions is sorted; count via binary search bounds for O(log n).
        count = _count_in_range(positions, lo, hi)
        if count > best_count:
            best_count = count
            best_center = center

    start = max(0, best_center - half)
    end = min(len(text), start + max_chars)
    if end - start < max_chars:  # clamped at the right edge; pull start back
        start = max(0, end - max_chars)
    return text[start:end]


# Skip ultra-common English words that drown out the signal.
_STOPWORDS = frozenset(
    "this that these those with from have been will would could should about "
    "their there which while where when what whom whose been being into onto "
    "your yours over under more most some many much such other another both "
    "also they them then than were ".split()
)


def _extract_keywords(statement: str) -> list[str]:
    """Pick distinctive words from `statement` for evidence search.

    Lower-cased, deduplicated, length ≥ 4, stop-words removed. We keep proper
    nouns and any token containing a digit (catches dollar amounts, versions).
    """
    raw = statement.lower().split()
    seen: set[str] = set()
    out: list[str] = []
    for w in raw:
        cleaned = "".join(c for c in w if c.isalnum() or c == "-" or c == "$")
        if not cleaned or cleaned in seen or cleaned in _STOPWORDS:
            continue
        # Keep short tokens only if numeric (e.g. "27", "$4m").
        if len(cleaned) < 4 and not any(ch.isdigit() for ch in cleaned):
            continue
        seen.add(cleaned)
        out.append(cleaned)
    return out


def _find_all(haystack: str, needle: str) -> list[int]:
    out: list[int] = []
    if not needle:
        return out
    i = 0
    while True:
        i = haystack.find(needle, i)
        if i < 0:
            return out
        out.append(i)
        i += len(needle)


def _count_in_range(sorted_positions: list[int], lo: int, hi: int) -> int:
    from bisect import bisect_left, bisect_right

    return bisect_right(sorted_positions, hi) - bisect_left(sorted_positions, lo)
