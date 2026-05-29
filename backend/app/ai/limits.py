"""Pipeline caps for extraction volume — balanced across user topics."""

from __future__ import annotations

from uuid import UUID


def sources_per_topic_cap(*, total_slots: int, topic_count: int) -> int:
    """Equal ceiling: each topic may use at most this many source slots."""
    if topic_count <= 0:
        return max(1, total_slots)
    return max(1, (total_slots + topic_count - 1) // topic_count)


def _topic_key(topic: str | None) -> str:
    return (topic or "").lower().strip()


def balanced_select_sources(
    pairs: list[tuple[UUID, str]],
    *,
    topics: list[str],
    limit: int,
    source_topics: dict[UUID, str | None],
    scores: dict[UUID, float] | None = None,
) -> list[tuple[UUID, str]]:
    """Select sources with an equal per-topic cap (best score within each topic)."""
    if limit <= 0 or not pairs:
        return []
    if not topics:
        ranked = list(pairs)
        if scores:
            ranked.sort(key=lambda p: scores.get(p[0], 0.0), reverse=True)
        return ranked[:limit]

    per_topic = sources_per_topic_cap(total_slots=limit, topic_count=len(topics))
    score_map = scores or {}
    topic_keys = [_topic_key(t) for t in topics]

    by_topic: dict[str, list[tuple[UUID, str]]] = {k: [] for k in topic_keys}
    for pair in pairs:
        key = _topic_key(source_topics.get(pair[0]))
        if key in by_topic:
            by_topic[key].append(pair)

    for key in by_topic:
        by_topic[key].sort(key=lambda p: score_map.get(p[0], 0.0), reverse=True)

    selected: list[tuple[UUID, str]] = []
    selected_ids: set[UUID] = set()
    counts = {k: 0 for k in topic_keys}

    while len(selected) < limit:
        added = False
        for topic in topics:
            if len(selected) >= limit:
                break
            key = _topic_key(topic)
            if counts[key] >= per_topic:
                continue
            for pair in by_topic[key]:
                if pair[0] in selected_ids:
                    continue
                selected.append(pair)
                selected_ids.add(pair[0])
                counts[key] += 1
                added = True
                break
        if not added:
            break

    return selected


def select_sources_for_extract(
    url_sources: list[tuple[UUID, str]],
    research_sources: list[tuple[UUID, str]],
    *,
    limit: int,
    research_scores: dict[UUID, float] | None = None,
    research_topics: dict[UUID, str] | None = None,
    url_topics: dict[UUID, str | None] | None = None,
    required_topics: list[str] | None = None,
) -> tuple[list[tuple[UUID, str]], int]:
    """Choose sources for LLM extract — balanced evenly across user topics when set.

    When *required_topics* is provided, each topic receives at most
    ``ceil(limit / len(topics))`` slots and selection round-robins across topics
    (best score within each topic). Otherwise URL sources are kept first, then
    research ranked by score.
    """
    if limit <= 0:
        dropped = len(url_sources) + len(research_sources)
        return [], dropped

    if required_topics:
        combined = list(url_sources) + list(research_sources)
        topic_map: dict[UUID, str | None] = {}
        if url_topics:
            topic_map.update(url_topics)
        if research_topics:
            topic_map.update(research_topics)
        scores = dict(research_scores or {})
        for uid, _ in url_sources:
            scores.setdefault(uid, 1.0)
        selected = balanced_select_sources(
            combined,
            topics=required_topics,
            limit=limit,
            source_topics=topic_map,
            scores=scores,
        )
        dropped = len(combined) - len(selected)
        return selected, dropped

    selected = list(url_sources[:limit])
    selected_ids = {pair[0] for pair in selected}
    slots = limit - len(selected)
    if slots <= 0:
        dropped = max(0, len(url_sources) - limit) + len(research_sources)
        return selected, dropped

    research = [p for p in research_sources if p[0] not in selected_ids]
    scores = research_scores or {}
    research.sort(key=lambda p: scores.get(p[0], 0.0), reverse=True)
    selected.extend(research[:slots])

    total = len(url_sources) + len(research_sources)
    dropped = max(0, total - len(selected))
    return selected, dropped


def remaining_extract_slots_by_topic(
    *,
    topics: list[str],
    total_limit: int,
    used_by_topic: dict[str, int],
) -> int:
    """How many research extract slots remain after URL extracts per topic."""
    if not topics:
        return total_limit
    per_topic = sources_per_topic_cap(total_slots=total_limit, topic_count=len(topics))
    remaining = 0
    for topic in topics:
        used = used_by_topic.get(_topic_key(topic), 0)
        remaining += max(0, per_topic - used)
    return min(remaining, total_limit)
