"""Unit tests for change detection."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from app.ai.diff import apply_change_detection, claim_hash
from app.ai.schemas import Insight, Report, Theme


def _report(*statements: str) -> Report:
    return Report(
        themes=[
            Theme(
                title="Theme",
                summary="s",
                insights=[
                    Insight(statement=s, citations=[uuid4()]) for s in statements
                ],
            )
        ],
        topics=["x"],
        source_count=1,
        generated_at=datetime.now(UTC),
    )


def test_identical_rerun_all_unchanged() -> None:
    report = _report("Acme Corp raised Series B funding in 2024")
    h = claim_hash("Acme Corp raised Series B funding in 2024")
    out = apply_change_detection(report, {h: "Acme Corp raised Series B funding in 2024"})
    assert out.themes[0].insights[0].diff_tag == "unchanged"
    assert out.removed_insights == []


def test_new_claim_tagged() -> None:
    report = _report("New insight about market share")
    prior = {claim_hash("Old insight only"): "Old insight only"}
    out = apply_change_detection(report, prior)
    assert out.themes[0].insights[0].diff_tag == "new"
    assert len(out.removed_insights) == 1
    assert out.removed_insights[0].diff_tag == "removed"


def test_removed_ghost_insights() -> None:
    report = _report("Only current claim here")
    prior_hash = claim_hash("Dropped from prior run")
    out = apply_change_detection(report, {prior_hash: "Dropped from prior run"})
    assert out.removed_insights[0].statement == "Dropped from prior run"
    assert out.removed_insights[0].diff_tag == "removed"
