"""Primary source attribution and boilerplate fact filtering."""

from __future__ import annotations

import pytest

from app.ai.fact_filter import filter_facts, is_low_value_fact
from app.ai.schemas import Fact, SearchResult
from app.ai.topic_match import source_primary_for_topic


@pytest.mark.unit
def test_micron_url_is_not_primary_nvidia_source() -> None:
    result = SearchResult(
        url="https://www.micron.com/news/hbm4",
        title="Micron ships HBM4 for NVIDIA Vera Rubin",
        snippet="Micron began volume shipments designed for NVIDIA Vera Rubin.",
        score=0.9,
    )
    assert not source_primary_for_topic(result, "nvidia", ["micron", "sandisk", "nvidia"])


@pytest.mark.unit
def test_nvidia_domain_is_primary_nvidia_source() -> None:
    result = SearchResult(
        url="https://nvidianews.nvidia.com/news/gtc-2026",
        title="GTC announcements",
        snippet="New platform details for AI data centers.",
        score=0.9,
    )
    assert source_primary_for_topic(result, "nvidia", ["micron", "sandisk", "nvidia"])


@pytest.mark.unit
def test_filter_drops_trademark_boilerplate_fact() -> None:
    facts = [
        Fact(
            claim="SanDisk communications include trademark and copyright statements.",
            evidence="© 2026 SanDisk Corporation. Trademark usage guidelines apply.",
            confidence="high",
        ),
        Fact(
            claim="SanDisk announced SANDISK Optimus as its internal SSD lineup.",
            evidence="Sandisk announced SANDISK Optimus as the new name for its internal SSD lineup.",
            confidence="high",
        ),
    ]
    kept = filter_facts(facts)
    assert len(kept) == 1
    assert "Optimus" in kept[0].claim


@pytest.mark.unit
def test_is_low_value_fact_detects_contact_blocks() -> None:
    assert is_low_value_fact(
        Fact(
            claim="Media contact email is mediainquiries@sandisk.com.",
            evidence="For media inquiries contact mediainquiries@sandisk.com.",
            confidence="medium",
        )
    )
