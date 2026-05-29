"""Unit tests for shared section definitions and research prompt builder."""

from __future__ import annotations

from app.ai.prompts.sections import build_research_user_prompt
from app.guardrails.wrapping import wrap_topics


def test_build_research_user_prompt_includes_keywords_and_dynamic_planning() -> None:
    topics = ["meta", "google"]
    prompt = build_research_user_prompt(topics)

    assert "USER KEYWORDS" in prompt
    assert wrap_topics(topics) in prompt
    assert "infer 4–6 analysis dimensions" in prompt
    assert "at least one search per keyword" in prompt
    assert "RESEARCH_DATE:" in prompt
    assert "ANALYSIS DIMENSIONS" not in prompt


def test_build_research_user_prompt_single_topic() -> None:
    prompt = build_research_user_prompt(["Acme Corp"])
    assert "<topic>Acme Corp</topic>" in prompt
    assert "entity type" in prompt
