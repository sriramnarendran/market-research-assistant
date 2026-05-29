"""Drop low-value extracted facts (legal footers, contact blocks, etc.)."""

from __future__ import annotations

import re

from app.ai.schemas import Fact

_BOILERPLATE_RE = re.compile(
    r"|".join(
        (
            r"\btrademark(s)?\b",
            r"\bcopyright\b",
            r"©",
            r"\(c\)\s*\d{4}",
            r"usage guideline",
            r"trademark and usage",
            r"mediainquiries@",
            r"investors@",
            r"press release contact",
            r"all rights reserved",
            r"subject to change without notice",
            r"not all products may be available",
        )
    ),
    re.IGNORECASE,
)


def is_low_value_fact(fact: Fact) -> bool:
    """True when a fact is legal/contact boilerplate, not market intelligence."""
    text = f"{fact.claim} {fact.evidence or ''}"
    if not text.strip():
        return True
    if _BOILERPLATE_RE.search(text) and not _has_substantive_signal(text):
        return True
    return False


def _has_substantive_signal(text: str) -> bool:
    """Keep facts that mention real product/business terms alongside legal text."""
    lowered = text.lower()
    signals = (
        "launch",
        "announced",
        "revenue",
        "ship",
        "product",
        "gb",
        "tb",
        "ssd",
        "hbm",
        "gpu",
        "earnings",
        "partnership",
        "acquisition",
    )
    return any(s in lowered for s in signals)


def filter_facts(facts: list[Fact]) -> list[Fact]:
    return [f for f in facts if not is_low_value_fact(f)]
