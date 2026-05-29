"""URL-only synthesis guidance and section retention."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from app.ai.agents.synth import _build_user_prompt
from app.ai.dedupe import dedupe_report
from app.ai.prompts.sections import build_synth_user_note
from app.ai.schemas import Fact, Insight, InsightSection, Report


def test_url_only_synth_note_requires_section_coverage() -> None:
    note = build_synth_user_note(topics=[])
    assert "URL-ONLY RUN" in note
    assert "market_trends" in note
    assert "consumer_behavior" in note
    assert "competitors[]" in note


def test_topic_synth_note_restricts_competitor_names() -> None:
    note = build_synth_user_note(topics=["google", "amazon"])
    assert "ONLY allowed competitors[] row names" in note
    assert "URL-ONLY" not in note


def test_build_user_prompt_includes_url_only_note() -> None:
    sid = uuid4()
    prompt = _build_user_prompt(
        [
            Fact(
                claim="Microsoft reported AI adoption trends.",
                evidence="More than 30% of US adults use AI.",
                confidence="high",
                source_id=sid,
            )
        ],
        [],
        source_count=1,
    )
    assert "URL-ONLY RUN" in prompt
    assert "TOPICS:" in prompt


def test_dedupe_keeps_market_trends_with_one_unique_insight() -> None:
    sid = uuid4()
    finding = "Microsoft found more than 30% of US working-age adults use AI."
    trend = "National AI adoption rose three points since end of 2025 per Microsoft."
    report = Report(
        headline="AI adoption climbs nationally",
        executive_summary="Summary " * 20,
        key_findings=[Insight(statement=finding, citations=[sid])],
        market_trends=InsightSection(
            summary="US AI adoption is broadening unevenly across geographies.",
            insights=[Insight(statement=trend, citations=[sid])],
        ),
        topics=[],
        source_count=1,
        generated_at=datetime.now(UTC),
    )
    out = dedupe_report(report)
    assert out.market_trends is not None
    assert len(out.market_trends.insights) == 1
