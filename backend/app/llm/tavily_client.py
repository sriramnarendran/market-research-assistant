"""Thin async wrapper around the Tavily Search API.

Returns raw `SearchResult` Pydantic models so the agent layer doesn't depend
on Tavily's internal dict shape.
"""

from __future__ import annotations

from typing import Any, Protocol

from app.ai.schemas import SearchResult
from app.ai.recency import tavily_search_kwargs
from app.core.config import get_settings


class TavilyClient(Protocol):
    """Protocol implemented by the real Tavily client and any test doubles."""

    async def search(
        self,
        *,
        query: str,
        max_results: int = 5,
        search_depth: str = "advanced",
    ) -> list[SearchResult]:
        ...


class LiveTavilyClient:
    """Real Tavily client. Uses the official `tavily-python` SDK."""

    def __init__(self, api_key: str | None = None) -> None:
        from tavily import AsyncTavilyClient

        self._client = AsyncTavilyClient(api_key=api_key or get_settings().TAVILY_API_KEY)

    async def search(
        self,
        *,
        query: str,
        max_results: int = 5,
        search_depth: str = "advanced",
    ) -> list[SearchResult]:
        settings = get_settings()
        kwargs: dict[str, Any] = {
            "query": query,
            "max_results": max_results,
            "search_depth": search_depth,
            "include_answer": False,
            "include_raw_content": False,
            **tavily_search_kwargs(settings),
        }
        response: dict[str, Any] = await self._client.search(**kwargs)
        raw_results = response.get("results") or []
        return [
            SearchResult(
                url=r.get("url", ""),
                title=r.get("title", ""),
                snippet=r.get("content", ""),
                score=float(r.get("score", 0.0)),
            )
            for r in raw_results
            if r.get("url")
        ]


class StubTavilyClient:
    """In-memory stub used when LLM_MODE=test or in unit tests."""

    def __init__(self, scripted: list[SearchResult] | None = None) -> None:
        self._scripted = scripted or []
        self.calls: list[str] = []

    async def search(
        self,
        *,
        query: str,
        max_results: int = 5,
        search_depth: str = "advanced",
    ) -> list[SearchResult]:
        self.calls.append(query)
        return self._scripted[:max_results]


def get_tavily_client() -> TavilyClient:
    """Factory used by the FastAPI app + worker."""
    settings = get_settings()
    if settings.LLM_MODE == "test":
        return StubTavilyClient()
    return LiveTavilyClient()
