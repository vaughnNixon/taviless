"""Multi-engine search gateway coordinating SearXNG and DuckDuckGo engines."""

from __future__ import annotations

import logging
from typing import List, Optional

from taviless.engines.base import BaseSearchEngine
from taviless.engines.duckduckgo import DuckDuckGoEngine
from taviless.engines.searxng import SearXNGEngine
from taviless.types import SearchResult

logger = logging.getLogger(__name__)


class MultiEngineGateway(BaseSearchEngine):
    """Orchestrates resilient search queries across SearXNG and DuckDuckGo."""

    def __init__(
        self,
        searxng_url: Optional[str] = None,
        default_engine: Optional[str] = None,
        timeout: float = 5.0,
    ) -> None:
        self.default_engine = (default_engine or "auto").lower()
        self.searxng = SearXNGEngine(custom_url=searxng_url, timeout=min(3.0, timeout))
        self.duckduckgo = DuckDuckGoEngine(timeout=timeout)

    def search(
        self,
        query: str,
        max_results: int = 5,
        include_domains: Optional[List[str]] = None,
        exclude_domains: Optional[List[str]] = None,
        time_range: Optional[str] = None,
    ) -> List[SearchResult]:
        """Execute search with intelligent fallback."""
        # If user explicitly chose duckduckgo
        if self.default_engine == "duckduckgo":
            return self.duckduckgo.search(
                query,
                max_results=max_results,
                include_domains=include_domains,
                exclude_domains=exclude_domains,
                time_range=time_range,
            )

        # If user explicitly chose searxng
        if self.default_engine == "searxng":
            results = self.searxng.search(
                query,
                max_results=max_results,
                include_domains=include_domains,
                exclude_domains=exclude_domains,
                time_range=time_range,
            )
            if results:
                return results
            logger.warning("SearXNG returned no results, falling back to DuckDuckGo.")

        # Default "auto" mode:
        # If a custom SearXNG instance is specified, try it first
        if self.searxng.custom_url:
            results = self.searxng.search(
                query,
                max_results=max_results,
                include_domains=include_domains,
                exclude_domains=exclude_domains,
                time_range=time_range,
            )
            if results:
                return results

        # Try SearXNG public gateways
        results = self.searxng.search(
            query,
            max_results=max_results,
            include_domains=include_domains,
            exclude_domains=exclude_domains,
            time_range=time_range,
        )
        if results:
            return results

        # Fallback to DuckDuckGo (highly resilient)
        logger.debug("SearXNG gateways unavailable or returned empty; using DuckDuckGo.")
        return self.duckduckgo.search(
            query,
            max_results=max_results,
            include_domains=include_domains,
            exclude_domains=exclude_domains,
            time_range=time_range,
        )


__all__ = [
    "BaseSearchEngine",
    "DuckDuckGoEngine",
    "MultiEngineGateway",
    "SearXNGEngine",
]
