"""User URL topic inference when counts match."""

from __future__ import annotations

import pytest

from app.ai.pipeline import _topic_for_user_url


@pytest.mark.unit
def test_url_topic_by_index_when_counts_match() -> None:
    topics = ["google", "microsoft", "amazon"]
    assert (
        _topic_for_user_url(
            topics=topics,
            url_index=2,
            url_count=3,
            title="Weekly digest",
            text="Generic cloud industry trends.",
        )
        == "amazon"
    )


@pytest.mark.unit
def test_url_topic_from_content_over_index() -> None:
    topics = ["google", "microsoft", "amazon"]
    assert (
        _topic_for_user_url(
            topics=topics,
            url_index=0,
            url_count=3,
            title="AWS Bedrock update",
            text="Amazon Web Services announced new models.",
        )
        == "amazon"
    )
