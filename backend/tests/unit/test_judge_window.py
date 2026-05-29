"""Judge excerpt-window selection.

The pre-fix behaviour returned a 1200-char window around the first keyword
match, which dropped the paragraph that supported the insight whenever the
keyword also appeared earlier in the document. The new behaviour returns
the source whole when it fits, otherwise picks the densest keyword cluster.
"""

from __future__ import annotations

import pytest

from app.ai.agents.judge import EXCERPT_MAX_CHARS, _select_window


@pytest.mark.unit
def test_returns_source_whole_when_under_budget() -> None:
    text = "alpha beta gamma " * 100  # ~1.7k chars, well under the cap
    out = _select_window(text, "alpha beta")
    assert out == text


@pytest.mark.unit
def test_picks_densest_cluster_over_first_match() -> None:
    """A common keyword in the intro must not pin the window when the dense
    evidence is later in the document."""
    intro = "Anthropic blog post. " + "filler text " * 200  # ~2.6k chars
    middle = "x" * (EXCERPT_MAX_CHARS // 2)
    dense = (
        "Anthropic committed $100 million in Mythos Preview credits. "
        "Mythos Preview discovered a 27-year-old OpenBSD bug and a 16-year-old "
        "FFmpeg bug. Anthropic donated $4 million to Alpha-Omega and OpenSSF. "
    ) * 10
    tail = "x" * (EXCERPT_MAX_CHARS // 2)
    text = intro + middle + dense + tail
    assert len(text) > EXCERPT_MAX_CHARS

    statement = (
        "Anthropic committed $100 million in Mythos Preview credits and $4 "
        "million to Alpha-Omega and OpenSSF, including discovery of a "
        "27-year-old OpenBSD bug."
    )
    out = _select_window(text, statement)
    assert len(out) <= EXCERPT_MAX_CHARS
    # The window should contain the specific evidence, not just the intro.
    assert "100 million" in out
    assert "OpenBSD" in out
    assert "Alpha-Omega" in out


@pytest.mark.unit
def test_no_keywords_returns_prefix() -> None:
    text = "x" * (EXCERPT_MAX_CHARS * 2)
    out = _select_window(text, "")  # no keywords
    assert len(out) == EXCERPT_MAX_CHARS


@pytest.mark.unit
def test_empty_text_returns_empty() -> None:
    assert _select_window("", "anything") == ""
