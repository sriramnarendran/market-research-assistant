"""Synthesis agent.

Single call that takes the merged `Fact[]` from extract + research phases and
produces a structured `Report` (themes + competitor activity). An
`@output_validator` enforces that every cited `source_id` exists in this run;
if the model fabricates a citation, we raise `ModelRetry` and the framework
re-prompts the model with the error message.
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from uuid import UUID

from pydantic_ai import Agent, ModelRetry, RunContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.budget import TokenBudget
from app.ai.deps import SynthDeps
from app.ai.dedupe import dedupe_report
from app.ai.topic_scope import scope_report_to_topics
from app.ai.models import get_synth_model
from app.ai.prompts import SYNTH_SYSTEM_PROMPT
from app.ai.schemas import Fact, Report
from app.ai.usage_recorder import record_usage
from app.core.llm_logger import log_llm_call
from app.ai.recency import recency_context_block
from app.ai.prompts.sections import build_synth_user_note
from app.guardrails.wrapping import wrap_topics

log = logging.getLogger(__name__)


def _build_agent() -> Agent[SynthDeps, Report]:
    agent: Agent[SynthDeps, Report] = Agent(
        model=get_synth_model(),
        deps_type=SynthDeps,
        output_type=Report,
        system_prompt=SYNTH_SYSTEM_PROMPT,
        retries=2,  # one extra so fabricated-citation retry has headroom
    )

    @agent.output_validator
    async def validate_citations(
        ctx: RunContext[SynthDeps], report: Report
    ) -> Report:
        valid = ctx.deps.valid_source_ids
        bad: list[str] = []

        def _check(citations: list[UUID]) -> None:
            for cid in citations:
                if cid not in valid:
                    bad.append(str(cid))

        for ins in report.key_findings:
            _check(ins.citations)
        for section in (report.market_trends, report.consumer_behavior):
            if section is not None:
                for ins in section.insights:
                    _check(ins.citations)
        for ins in report.opportunities:
            _check(ins.citations)
        for ins in report.risks:
            _check(ins.citations)
        for km in report.key_metrics:
            _check(km.citations)
        for theme in report.themes:
            for ins in theme.insights:
                _check(ins.citations)
        for ca in report.competitors:
            for ins in ca.insights:
                _check(ins.citations)
        if report.competitive_strategic_synthesis is not None:
            syn = report.competitive_strategic_synthesis
            for ins in syn.dynamics:
                _check(ins.citations)
            for ins in syn.implications:
                _check(ins.citations)

        if bad:
            sample = ", ".join(sorted(set(bad))[:5])
            raise ModelRetry(
                "Some citations reference source_ids that do not exist "
                f"in this run (e.g. {sample}). Use only the source_ids that "
                "appear in the input facts."
            )
        # Stamp the metadata fields the LLM does not control.
        report.topics = list(ctx.deps.topics)
        report.generated_at = datetime.now(UTC)
        return report

    return agent


async def synthesize_report(
    *,
    session: AsyncSession,
    run_id: UUID,
    facts: list[Fact],
    topics: list[str],
    source_count: int,
    budget: TokenBudget,
) -> Report:
    """Synthesise a structured report from merged facts."""
    budget.guard()
    valid_source_ids = {f.source_id for f in facts if f.source_id is not None}
    user_prompt = _build_user_prompt(facts, topics, source_count)

    agent = _build_agent()
    deps = SynthDeps(
        run_id=run_id,
        valid_source_ids=valid_source_ids,
        topics=list(topics),
        budget=budget,
    )
    start = time.monotonic()
    result = await agent.run(user_prompt, deps=deps)
    duration_ms = int((time.monotonic() - start) * 1000)

    counts = await record_usage(
        session,
        run_id=run_id,
        phase="synth",
        usage=result.usage(),
        duration_ms=duration_ms,
    )
    log_llm_call(run_id=run_id, phase="synth", result=result, duration_ms=duration_ms)
    budget.record(counts.input_tokens, counts.output_tokens)

    report = result.output
    report.source_count = source_count
    return scope_report_to_topics(dedupe_report(report), topics)


def _build_user_prompt(facts: list[Fact], topics: list[str], source_count: int) -> str:
    """Compose the user message: topics wrapped + facts serialised as JSON."""
    import json

    parts = [
        recency_context_block().rstrip(),
        "",
        "TOPICS:",
        wrap_topics(topics),
        "",
        f"SOURCE_COUNT: {source_count}",
        "",
        "SYNTHESIS_NOTE:",
        build_synth_user_note(topics=topics),
        "",
        "FACTS:",
        json.dumps(
            [
                {
                    "claim": f.claim,
                    "evidence": f.evidence,
                    "confidence": f.confidence,
                    "source_id": str(f.source_id) if f.source_id else None,
                }
                for f in facts
            ],
            indent=2,
        ),
    ]
    return "\n".join(parts)
