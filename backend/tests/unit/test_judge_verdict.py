"""JudgeVerdict schema normalization tests."""

from __future__ import annotations

import pytest

from app.ai.schemas import JudgeVerdict


@pytest.mark.unit
def test_judge_verdict_truncates_long_rationale() -> None:
    long_text = "x" * 500
    v = JudgeVerdict(verdict="verified", rationale=long_text)
    assert len(v.rationale) <= 400
    assert v.rationale.endswith("…")


@pytest.mark.unit
def test_judge_verdict_normalizes_verdict_case() -> None:
    v = JudgeVerdict(verdict="Verified", rationale="Excerpt states the fact.")  # type: ignore[arg-type]
    assert v.verdict == "verified"


@pytest.mark.unit
def test_judge_verdict_fallback_for_empty_rationale() -> None:
    v = JudgeVerdict(verdict="unsupported", rationale="  ")
    assert v.rationale == "No supporting excerpt found."
