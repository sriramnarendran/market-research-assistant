"""Typed dependency classes passed via Pydantic AI's `deps_type`.

These carry shared state (DB session, run id, token budget, Tavily client)
into agent runs and into every `@agent.tool` invocation via `RunContext`.

Kept as `@dataclass` rather than Pydantic models so we can hold non-serialisable
references (an async DB session, an httpx-backed client) without ConfigDict
acrobatics.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.ai.budget import TokenBudget
    from app.ai.schemas import CollectedSource
    from app.llm.tavily_client import TavilyClient


@dataclass
class SharedResearchState:
    """Cross-topic URL dedupe while research tasks run in parallel."""

    seen_urls: set[str] = field(default_factory=set)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


@dataclass(slots=True)
class ResearchDeps:
    """Injected into the research agent and its `search` tool.

    `iteration_count` and `collected` are mutated by the `search` tool on each
    invocation. The agent system prompt instructs the model to honour any
    `note` returned by a tool call (used to signal iteration cap / budget).

    For parallel per-topic research, each task uses `topics=[one keyword]` and
    sets `all_topics` to the full run list (for balanced caps). Pass `shared`
    so URL dedupe works across concurrent tasks.
    """

    run_id: UUID
    topics: list[str]
    tavily: TavilyClient
    budget: TokenBudget
    session: AsyncSession
    iteration_count: int = 0
    collected: list[CollectedSource] = field(default_factory=list)
    topics_with_sources: set[str] = field(default_factory=set)
    all_topics: list[str] | None = None
    shared: SharedResearchState | None = None


@dataclass(slots=True)
class ExtractDeps:
    """Injected into the per-source extract agent.

    `source_id` is stamped onto every returned `Fact` by an output_validator —
    the LLM never sees it and cannot fabricate citations to other sources.
    """

    source_id: UUID
    budget: TokenBudget


@dataclass(slots=True)
class SynthDeps:
    """Injected into the synthesis agent.

    `valid_source_ids` enables an output_validator to reject `Report` outputs
    whose insight citations reference non-existent sources.
    """

    run_id: UUID
    valid_source_ids: set[UUID]
    topics: list[str]
    budget: TokenBudget


@dataclass(slots=True)
class JudgeDeps:
    """Injected into the judge agent."""

    run_id: UUID
    budget: TokenBudget
