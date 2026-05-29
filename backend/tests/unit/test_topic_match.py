"""Unit tests for dynamic topic matching in research."""

from __future__ import annotations

from app.ai.schemas import SearchResult
from app.ai.topic_match import (
    filter_relevant_results,
    topic_for_text,
    topic_matches_text,
    uncovered_topics,
)


def test_compound_topic_matches_partial_product_name() -> None:
    text = "Google announces Gemini 2.5 Flash with improved reasoning."
    assert topic_matches_text("gemini flash 3.5", text)
    assert topic_for_text(text, ["claude opus 4.7", "gemini flash 3.5"]) == "gemini flash 3.5"


def test_single_token_topic_matches_in_text() -> None:
    assert topic_matches_text("amazon", "Amazon announced a major AWS update")
    assert topic_for_text("Amazon Web Services update", ["google", "amazon"]) == "amazon"


def test_filter_trusts_targeted_query_without_snippet_match() -> None:
    results = [
        SearchResult(
            url="https://aws.amazon.com/news",
            title="AWS announces agent tooling",
            snippet="New Bedrock features for enterprise agents.",
            score=0.9,
        ),
    ]
    kept = filter_relevant_results(
        results,
        ["google", "microsoft", "amazon"],
        score_min=0.5,
        query="amazon AWS AI agents 2026",
    )
    assert len(kept) == 1


def test_topic_for_text_returns_empty_when_no_match() -> None:
    assert topic_for_text("unrelated sector trends", ["google", "amazon"]) == ""


def test_uncovered_topics() -> None:
    assert uncovered_topics(["google", "amazon"], {"google"}) == ["amazon"]


def test_filter_accepts_top_hit_for_dedicated_query() -> None:
    results = [
        SearchResult(
            url="https://example.com/roundup",
            title="Big tech week in review",
            snippet="Cloud vendors compete on AI agents and chips.",
            score=0.88,
        ),
    ]
    kept = filter_relevant_results(
        results,
        ["amazon"],
        score_min=0.5,
        query="amazon company latest news products 2026",
        accept_top_hit_if_empty=True,
    )
    assert len(kept) == 1
