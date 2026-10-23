"""Multi-engine search gateway coordinating SearXNG and DuckDuckGo engines."""

from __future__ import annotations

import concurrent.futures
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

        # Default "auto" mode: Speculative parallel race between engines.
        # Queries DuckDuckGo and SearXNG simultaneously to eliminate failover latency.
        # Whichever returns non-empty results first wins; the other is given a 0.25s grace
        # window to merge its results before being cut off.
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
        combined_results: List[SearchResult] = []
        try:
            fut_ddg = executor.submit(
                self.duckduckgo.search,
                query,
                max_results=max_results,
                include_domains=include_domains,
                exclude_domains=exclude_domains,
                time_range=time_range,
            )
            fut_searx = executor.submit(
                self.searxng.search,
                query,
                max_results=max_results,
                include_domains=include_domains,
                exclude_domains=exclude_domains,
                time_range=time_range,
            )

            winner_fut = None
            for fut in concurrent.futures.as_completed([fut_ddg, fut_searx]):
                try:
                    res = fut.result()
                except Exception as exc:
                    logger.debug("Engine failed in speculative race: %s", exc)
                    res = []

                if res:
                    combined_results.extend(res)
                    winner_fut = fut
                    break

            # If an engine finished with results, give the second engine a tight 0.25s cutoff
            other_fut = fut_searx if winner_fut is fut_ddg else fut_ddg
            if winner_fut and other_fut:
                try:
                    extra = other_fut.result(timeout=0.25)
                    if extra:
                        combined_results.extend(extra)
                except (concurrent.futures.TimeoutError, Exception):
                    # Cut off lagging engine immediately
                    pass

        finally:
            executor.shutdown(wait=False, cancel_futures=True)

        return self.filter_and_rank(
            combined_results,
            max_results=max_results,
            include_domains=include_domains,
            exclude_domains=exclude_domains,
        )


__all__ = [
    "BaseSearchEngine",
    "DuckDuckGoEngine",
    "MultiEngineGateway",
    "SearXNGEngine",
]
