"""Unit tests for post-synth topic scoping."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from app.ai.schemas import CompetitorActivity, Insight, KeyMetric, Report
from app.ai.topic_scope import scope_report_to_topics


def test_scope_drops_non_user_competitors() -> None:
    sid = uuid4()
    report = Report(
        headline="KPMG embeds Claude across 276,000 staff",
        competitors=[
            CompetitorActivity(
                competitor="google",
                insights=[Insight(statement="Google launched Gemini 3.5 Flash.", citations=[sid])],
            ),
            CompetitorActivity(
                competitor="Anthropic",
                insights=[Insight(statement="Anthropic partnered with KPMG.", citations=[sid])],
            ),
        ],
        topics=["google", "microsoft", "amazon"],
        source_count=1,
        generated_at=datetime.now(UTC),
    )
    out = scope_report_to_topics(report, ["google", "microsoft", "amazon"])
    assert [c.competitor for c in out.competitors] == ["google"]


def test_scope_rewrites_headline_to_user_topic() -> None:
    sid = uuid4()
    report = Report(
        headline="KPMG embeds Claude across 276,000 staff",
        key_findings=[
            Insight(statement="Google launched Gemini 3.5 Flash broadly.", citations=[sid]),
            Insight(statement="KPMG announced Claude deployment.", citations=[sid]),
        ],
        topics=["google"],
        source_count=1,
        generated_at=datetime.now(UTC),
    )
    out = scope_report_to_topics(report, ["google"])
    assert "Google launched Gemini" in out.headline
