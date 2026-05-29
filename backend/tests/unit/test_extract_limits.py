"""Source selection caps for extraction."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.ai.limits import (
    balanced_select_sources,
    remaining_extract_slots_by_topic,
    select_sources_for_extract,
    sources_per_topic_cap,
)


@pytest.mark.unit
def test_sources_per_topic_cap_divides_evenly() -> None:
    assert sources_per_topic_cap(total_slots=8, topic_count=3) == 3
    assert sources_per_topic_cap(total_slots=6, topic_count=3) == 2


@pytest.mark.unit
def test_urls_take_priority_without_topics() -> None:
    u1, u2 = uuid4(), uuid4()
    r1, r2 = uuid4(), uuid4()
    selected, dropped = select_sources_for_extract(
        [(u1, "a"), (u2, "b")],
        [(r1, "c"), (r2, "d")],
        limit=3,
        research_scores={r1: 0.9, r2: 0.1},
    )
    assert len(selected) == 3
    assert selected[0][0] == u1
    assert selected[1][0] == u2
    assert selected[2][0] == r1
    assert dropped == 1


@pytest.mark.unit
def test_research_ranked_by_score_without_topics() -> None:
    r1, r2, r3 = uuid4(), uuid4(), uuid4()
    selected, dropped = select_sources_for_extract(
        [],
        [(r1, "a"), (r2, "b"), (r3, "c")],
        limit=2,
        research_scores={r1: 0.5, r2: 0.99, r3: 0.7},
    )
    assert [p[0] for p in selected] == [r2, r3]
    assert dropped == 1


@pytest.mark.unit
def test_balanced_extract_limits_dominant_topic() -> None:
    """Micron cannot take all slots when 3 topics compete."""
    micron = [uuid4() for _ in range(5)]
    sandisk = [uuid4() for _ in range(2)]
    nvidia = [uuid4() for _ in range(2)]
    pairs = (
        [(mid, "m") for mid in micron]
        + [(sid, "s") for sid in sandisk]
        + [(nid, "n") for nid in nvidia]
    )
    topics = {
        **{mid: "micron" for mid in micron},
        **{sid: "sandisk" for sid in sandisk},
        **{nid: "nvidia" for nid in nvidia},
    }
    scores = {mid: 0.99 for mid in micron} | {sid: 0.5 for sid in sandisk} | {nid: 0.5 for nid in nvidia}

    selected = balanced_select_sources(
        pairs,
        topics=["micron", "sandisk", "nvidia"],
        limit=8,
        source_topics=topics,
        scores=scores,
    )

    assert len(selected) == 7
    counts = {"micron": 0, "sandisk": 0, "nvidia": 0}
    for sid, _ in selected:
        counts[topics[sid]] += 1
    assert counts["micron"] <= 3
    assert counts["sandisk"] >= 2
    assert counts["nvidia"] >= 2


@pytest.mark.unit
def test_balanced_select_round_robins_across_topics() -> None:
    a, b, c = uuid4(), uuid4(), uuid4()
    selected = balanced_select_sources(
        [(a, "1"), (b, "2"), (c, "3")],
        topics=["alpha", "beta", "gamma"],
        limit=3,
        source_topics={a: "alpha", b: "beta", c: "gamma"},
        scores={a: 0.1, b: 0.9, c: 0.5},
    )
    assert {p[0] for p in selected} == {a, b, c}


@pytest.mark.unit
def test_remaining_research_slots_after_url_extract() -> None:
    remaining = remaining_extract_slots_by_topic(
        topics=["micron", "sandisk", "nvidia"],
        total_limit=8,
        used_by_topic={"micron": 3, "sandisk": 1},
    )
    assert remaining == 5
