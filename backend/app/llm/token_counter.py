"""Token counting for the URL fetch path.

Used only to truncate cleaned article text to fit a per-source budget; not
called for LLM-call accounting (Pydantic AI's `result.usage()` handles that).

Uses `tiktoken` with the `o200k_base` encoder — the same tokenizer family used
by GPT-4o / GPT-5. Falls back to a character-based heuristic if tiktoken is
unavailable for some reason, so the fetch path never blocks.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

_HEURISTIC_CHARS_PER_TOKEN = 4.0


@lru_cache(maxsize=1)
def _encoder() -> Any | None:
    """Build a tiktoken encoder once. Returns None if tiktoken is missing."""
    try:
        import tiktoken

        return tiktoken.get_encoding("o200k_base")
    except Exception:
        return None


def estimate_tokens(text: str) -> int:
    """Count tokens with tiktoken; falls back to a character heuristic."""
    if not text:
        return 0
    enc = _encoder()
    if enc is None:
        return max(1, int(len(text) / _HEURISTIC_CHARS_PER_TOKEN))
    return len(enc.encode(text, disallowed_special=()))


def truncate_to_token_budget(text: str, max_tokens: int) -> str:
    """Truncate `text` to roughly `max_tokens` tokens.

    Keeps the first ~7/8 and last ~1/8 of the budget so conclusions are not
    chopped off — articles often summarise findings at the end. When tiktoken
    is available we slice on token boundaries; otherwise we approximate via
    character ratios.
    """
    n = estimate_tokens(text)
    if n <= max_tokens:
        return text

    enc = _encoder()
    head_tokens = int(max_tokens * 7 / 8)
    tail_tokens = max_tokens - head_tokens
    marker = "\n\n[... content truncated to fit token budget ...]\n\n"

    if enc is not None:
        token_ids = enc.encode(text, disallowed_special=())
        head = enc.decode(token_ids[:head_tokens])
        tail = enc.decode(token_ids[-tail_tokens:]) if tail_tokens > 0 else ""
        return head + marker + tail

    head_chars = int(head_tokens * _HEURISTIC_CHARS_PER_TOKEN)
    tail_chars = int(tail_tokens * _HEURISTIC_CHARS_PER_TOKEN)
    if head_chars + tail_chars >= len(text):
        return text
    return text[:head_chars] + marker + text[-tail_chars:]
