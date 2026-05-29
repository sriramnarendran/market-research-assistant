"""Prompt-injection defence — wrap untrusted content before it hits an LLM.

Two flavours:
  - `wrap_source(source_id, text)`: wraps fetched article text in a
    `<source id="...">...</source>` block. Used by the extract agent.
  - `wrap_topic(topic)`: wraps user-supplied topics in `<topic>...</topic>`
    so injection attempts inside a topic string ("ignore previous
    instructions and ...") can be quoted but not interpreted as instructions.

Both functions escape `<` and `>` inside the payload so the model cannot
"close" our wrapping tag from inside the user content.
"""

from __future__ import annotations

from uuid import UUID


def _escape(payload: str) -> str:
    return payload.replace("<", "&lt;").replace(">", "&gt;")


def wrap_source(source_id: UUID | str, text: str) -> str:
    """Wrap source content with a tagged delimiter and escape angle brackets."""
    return f'<source id="{source_id}">\n{_escape(text)}\n</source>'


def wrap_topic(topic: str) -> str:
    return f"<topic>{_escape(topic)}</topic>"


def wrap_topics(topics: list[str]) -> str:
    """Join wrapped topics into a single block for inclusion in a user prompt."""
    return "\n".join(wrap_topic(t) for t in topics)


def wrap_excerpt(source_id: UUID | str, excerpt: str) -> str:
    """Wrap a short source excerpt used by the judge."""
    return f'<excerpt source_id="{source_id}">\n{_escape(excerpt)}\n</excerpt>'
