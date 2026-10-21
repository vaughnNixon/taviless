"""Type definitions for Tavily-compatible search results and configurations."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, TypedDict

SearchDepth = Literal["basic", "advanced"]


class SearchResult(TypedDict, total=False):
    """A single search result item matching Tavily's schema."""
    title: str
    url: str
    content: str
    score: float
    raw_content: Optional[str]


class SearchResponse(TypedDict, total=False):
    """The root search response matching Tavily's exact JSON schema."""
    query: str
    results: List[SearchResult]
    response_time: float
    answer: Optional[str]
    images: List[Dict[str, Any]]
