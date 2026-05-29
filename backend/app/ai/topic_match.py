"""Topic keyword matching for research relevance filtering."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from app.ai.schemas import SearchResult

_TOKEN_SPLIT = re.compile(r"[\s\-_/]+")
_VERSION_TOKEN = re.compile(r"^\d+(?:\.\d+)*$")


def _topic_tokens(topic: str) -> tuple[str, ...]:
    raw = _TOKEN_SPLIT.split(topic.lower().strip())
    return tuple(t for t in raw if t)


def _is_version_token(token: str) -> bool:
    return bool(_VERSION_TOKEN.match(token))


def _significant_tokens(topic: str) -> tuple[str, ...]:
    return tuple(
        t for t in _topic_tokens(topic) if not _is_version_token(t) and len(t) >= 2
    )


def _token_in_text(token: str, hay: str) -> bool:
    if len(token) <= 2:
        return token in hay
    return bool(re.search(rf"\b{re.escape(token)}\b", hay, re.IGNORECASE))


def canonical_topic(topic: str, topics: list[str]) -> str:
    """Map a matched label back to the user-supplied topic string."""
    key = topic.lower().strip()
    for user_topic in topics:
        if user_topic.lower().strip() == key:
            return user_topic
    return topic.strip()


def topic_matches_text(topic: str, text: str) -> bool:
    """True when significant tokens from *topic* appear in *text*."""
    hay = text.lower()
    key = topic.lower().strip()
    if key and key in hay:
        return True

    tokens = _significant_tokens(topic)
    if not tokens:
        return False

    matched = [t for t in tokens if _token_in_text(t, hay)]
    if not matched:
        return False
    if len(tokens) == 1:
        return True

    anchor = max(tokens, key=len)
    if _token_in_text(anchor, hay):
        if len(tokens) <= 2:
            return True
        required = max(1, (len(tokens) + 1) // 2)
        return len(matched) >= required

    return len(matched) >= max(2, (len(tokens) + 1) // 2)


def topic_for_text(text: str, topics: list[str]) -> str:
    """Return the first user topic whose tokens appear in text, else empty."""
    for topic in topics:
        if topic_matches_text(topic, text):
            return topic
    return ""


def topic_for_result(
    result: SearchResult,
    topics: list[str],
    *,
    query: str | None = None,
) -> str:
    """Attribute a search hit to a user topic; prefer the query's target keyword."""
    text = f"{result.title}\n{result.snippet}"
    if query:
        targeted = topics_targeted_by_query(query, topics)
        if len(targeted) == 1:
            return targeted[0]
    return topic_for_text(text, topics)


def topics_targeted_by_query(query: str, topics: list[str]) -> list[str]:
    return [topic for topic in topics if query_targets_topic(query, topic)]


def is_user_topic_name(name: str, topics: list[str]) -> bool:
    """True when *name* matches a user-supplied topic (case-insensitive)."""
    normalized = name.lower().strip()
    return any(t.lower().strip() == normalized for t in topics)


def query_targets_topic(query: str, topic: str) -> bool:
    return topic_matches_text(topic, query)


def url_matches_topic_domain(url: str, topic: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    if not host:
        return False
    for token in _significant_tokens(topic):
        if len(token) >= 4 and token in host:
            return True
    key = topic.lower().strip()
    return bool(key and key in host)


def source_primary_for_topic(
    result: SearchResult,
    topic: str,
    topics: list[str],
) -> bool:
    """True when a hit is a primary source for *topic*, not another keyword's site."""
    canonical = canonical_topic(topic, topics)
    if url_matches_topic_domain(result.url, canonical):
        return True
    text = f"{result.title}\n{result.snippet}"
    if not topic_matches_text(canonical, text):
        return False
    for other in topics:
        other_key = other.lower().strip()
        if other_key == canonical.lower().strip():
            continue
        if url_matches_topic_domain(result.url, other):
            return False
    return True


def uncovered_topics(topics: list[str], covered: set[str]) -> list[str]:
    covered_keys = {canonical_topic(c, topics).lower() for c in covered}
    return [t for t in topics if t.lower() not in covered_keys]


def is_topic_covered(topic: str, topics: list[str], covered: set[str]) -> bool:
    return canonical_topic(topic, topics).lower() in {
        canonical_topic(c, topics).lower() for c in covered
    }


def filter_relevant_results(
    results: list[SearchResult],
    topics: list[str],
    *,
    score_min: float,
    query: str | None = None,
    attributed_topic: str | None = None,
    accept_top_hit_if_empty: bool = False,
) -> list[SearchResult]:
    """Score gate + optional topic match.

    When *attributed_topic* is set or the query targets a single keyword, trust
    Tavily scores — the LLM already crafted an entity-specific query.
    """
    targeted_list = topics_targeted_by_query(query, topics) if query else []
    targeted = targeted_list[0] if len(targeted_list) == 1 else None
    trust_query = attributed_topic is not None or targeted is not None

    kept: list[SearchResult] = []
    for result in results:
        if result.score < score_min:
            continue
        if trust_query:
            kept.append(result)
            continue
        haystack = f"{result.title}\n{result.snippet}"
        if any(topic_matches_text(topic, haystack) for topic in topics):
            kept.append(result)

    if not kept and trust_query and accept_top_hit_if_empty:
        eligible = [r for r in results if r.score >= score_min]
        if eligible:
            kept = [max(eligible, key=lambda r: r.score)]

    return kept
