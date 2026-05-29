"""Unit tests for post-synthesis report deduplication."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from app.ai.dedupe import dedupe_report
from app.ai.schemas import (
    CompetitiveStrategicSynthesis,
    CompetitorActivity,
    Insight,
    Report,
    Theme,
)


def _ins(statement: str) -> Insight:
    return Insight(statement=statement, citations=[uuid4()])


def test_dedupe_removes_repeated_sections() -> None:
    google_gemini = (
        "Google launched Gemini 3.5 Flash and made it generally available via "
        "Google Antigravity, the Gemini API, and Android Studio."
    )
    meta_horizon = (
        "Meta reported Horizon+ exceeded 1 million active subscribers in 2025."
    )
    cross = (
        "Google announced Gemini 3.5 Flash at I/O 2026, while Meta reported "
        "Horizon+ surpassed 1 million subscribers in 2025."
    )

    report = Report(
        headline="Headline",
        executive_summary="Summary " * 20,
        key_findings=[_ins(google_gemini), _ins(meta_horizon)],
        themes=[
            Theme(
                title="AI models",
                summary="Both companies advanced AI.",
                insights=[_ins(google_gemini), _ins("Unique theme-only insight about ads.")],
            )
        ],
        competitors=[
            CompetitorActivity(
                competitor="Google",
                insights=[_ins(google_gemini), _ins("Google launched a $100 AI Ultra plan.")],
            ),
            CompetitorActivity(
                competitor="Meta",
                insights=[_ins(meta_horizon)],
            ),
        ],
        competitive_strategic_synthesis=CompetitiveStrategicSynthesis(
            summary="Cross-company narrative " * 10,
            dynamics=[_ins(google_gemini), _ins(cross)],
        ),
        topics=["google", "meta"],
        source_count=2,
        generated_at=datetime.now(UTC),
    )

    out = dedupe_report(report)

    assert len(out.key_findings) == 2
    assert len(out.themes) == 1
    assert len(out.themes[0].insights) == 1
    assert out.themes[0].insights[0].statement.startswith("Unique theme-only")
    assert len(out.competitors[0].insights) == 1
    assert "$100" in out.competitors[0].insights[0].statement
    assert out.competitive_strategic_synthesis is not None
    assert len(out.competitive_strategic_synthesis.dynamics) == 1
    assert "while Meta" in out.competitive_strategic_synthesis.dynamics[0].statement
