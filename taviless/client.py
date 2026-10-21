"""Main client interface for Taviless, offering 100% drop-in parity with Tavily."""

from __future__ import annotations

import concurrent.futures
import logging
import re
import time
from typing import Any, Dict, List, Optional

from taviless.engines import MultiEngineGateway
from taviless.extractor import fetch_and_extract
from taviless.types import SearchDepth, SearchResponse, SearchResult

logger = logging.getLogger(__name__)

TEMPORAL_KEYWORDS = re.compile(
    r"\b(latest|recent|newest|today|breaking|upcoming|this month|this week)\b",
    re.IGNORECASE,
)


class TavilyClient:
    """Drop-in replacement for official TavilyClient without requiring any API keys.

    Attributes:
        api_key: Optional API key string (accepted for drop-in compatibility, not required).
        searxng_url: Optional private SearXNG instance endpoint.
        default_engine: Preferred engine ("auto", "searxng", or "duckduckgo").
        request_timeout: Search engine request timeout in seconds.
        crawl_timeout: Webpage crawling timeout in seconds.
        max_workers: Thread pool concurrency limit for parallel extraction.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        searxng_url: Optional[str] = None,
        default_engine: Optional[str] = None,
        request_timeout: float = 6.0,
        crawl_timeout: float = 4.0,
        max_workers: int = 5,
        use_trafilatura: bool = True,
    ) -> None:
        self.api_key = api_key
        self.crawl_timeout = crawl_timeout
        self.max_workers = max_workers
        self.use_trafilatura = use_trafilatura
        self.gateway = MultiEngineGateway(
            searxng_url=searxng_url,
            default_engine=default_engine,
            timeout=request_timeout,
        )

    def search(
        self,
        query: str,
        search_depth: SearchDepth = "basic",
        max_results: int = 5,
        include_domains: Optional[List[str]] = None,
        exclude_domains: Optional[List[str]] = None,
        include_answer: bool = False,
        include_raw_content: bool = False,
        include_images: bool = False,
        time_range: Optional[str] = None,
    ) -> SearchResponse:
        """Execute a web search and return a Tavily-compatible JSON response.

        Args:
            query: The search query string.
            search_depth: "basic" for ultra-fast snippets, or "advanced" for full-page extraction.
            max_results: Maximum number of search results to return (default 5).
            include_domains: List of domains to whitelist in results.
            exclude_domains: List of domains to blacklist in results.
            include_answer: Whether to include a short synthesized answer string.
            include_raw_content: Whether to include full uncleaned HTML in raw_content field.
            include_images: Whether to include an images field.
            time_range: Optional time restriction ('day', 'week', 'month', 'year').

        Returns:
            Dictionary matching Tavily's exact JSON response structure.
        """
        start_time = time.time()

        if not query or not query.strip():
            return {
                "query": query,
                "results": [],
                "response_time": 0.0,
                "answer": None,
                "images": [],
            }

        # Auto-detect temporal intent if time_range wasn't explicitly passed
        is_temporal = bool(time_range) or bool(TEMPORAL_KEYWORDS.search(query))
        effective_time_range = time_range or ("month" if is_temporal else None)

        # Step 1: Fetch search engine results
        raw_results = self.gateway.search(
            query=query.strip(),
            max_results=max_results,
            include_domains=include_domains,
            exclude_domains=exclude_domains,
            time_range=effective_time_range,
        )

        results: List[SearchResult] = list(raw_results)

        # Auto-inferred time filter returned nothing: retry unfiltered
        if not results and effective_time_range and not time_range:
            results = list(
                self.gateway.search(
                    query=query.strip(),
                    max_results=max_results,
                    include_domains=include_domains,
                    exclude_domains=exclude_domains,
                    time_range=None,
                )
            )

        # Step 2: If advanced search depth is requested, crawl top pages in parallel
        if search_depth == "advanced" and results:
            results = self._crawl_and_extract_parallel(
                results,
                include_raw_content=include_raw_content,
                reverse_chronological=is_temporal,
            )

        elapsed = round(time.time() - start_time, 2)

        # Step 3: Formulate answer if requested
        answer: Optional[str] = None
        if include_answer and results:
            answer = self._synthesize_quick_answer(query, results)

        response: SearchResponse = {
            "query": query,
            "results": results,
            "response_time": elapsed,
            "answer": answer,
            "images": [],
        }
        return response

    def _crawl_and_extract_parallel(
        self,
        results: List[SearchResult],
        include_raw_content: bool = False,
        reverse_chronological: bool = False,
    ) -> List[SearchResult]:
        """Crawl the top links concurrently and extract clean, token-dense markdown content."""

        def _fetch_one(item: SearchResult) -> SearchResult:
            url = item.get("url", "")
            if not url:
                return item

            clean_text, raw_html = fetch_and_extract(
                url=url,
                timeout=self.crawl_timeout,
                max_chars=4000,
                use_trafilatura=self.use_trafilatura,
                reverse_chronological=reverse_chronological,
            )

            # If full page content was successfully extracted, replace snippet
            updated = dict(item)
            if clean_text and len(clean_text.strip()) > len(item.get("content", "")):
                updated["content"] = clean_text

            if include_raw_content:
                updated["raw_content"] = raw_html

            return updated  # type: ignore

        workers = min(len(results), self.max_workers)
        if workers <= 1:
            return [_fetch_one(r) for r in results]

        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            crawled = list(executor.map(_fetch_one, results))

        return crawled

    def _synthesize_quick_answer(self, query: str, results: List[SearchResult]) -> str:
        """Generate a concise extracted summary answer from top result content."""
        snippets: List[str] = []
        for r in results[:3]:
            content = r.get("content", "").strip()
            if content:
                # Take the first 1-2 sentences
                first_part = content.split("\n")[0]
                if len(first_part) > 200:
                    first_part = first_part[:200].rstrip() + "..."
                snippets.append(first_part)

        if snippets:
            return " | ".join(snippets)
        return "No direct answer found in extracted snippets."

    def get_search_context(
        self,
        query: str,
        search_depth: SearchDepth = "basic",
        max_results: int = 5,
        max_tokens: int = 4000,
    ) -> str:
        """Get formatted context string ready for LLM prompt injection (matches Tavily API)."""
        response = self.search(
            query=query,
            search_depth=search_depth,
            max_results=max_results,
        )
        context_parts: List[str] = []
        char_budget = max_tokens * 4  # Approximate 4 chars per token
        total_chars = 0

        for r in response.get("results", []):
            url = r.get("url", "")
            content = r.get("content", "")
            chunk = f"Source: {url}\nContent: {content}\n\n"
            if total_chars + len(chunk) > char_budget:
                remaining = char_budget - total_chars
                if remaining > 100:
                    context_parts.append(chunk[:remaining] + "...\n")
                break
            context_parts.append(chunk)
            total_chars += len(chunk)

        return "".join(context_parts).strip()

    def qna_search(
        self,
        query: str,
        search_depth: SearchDepth = "advanced",
        max_results: int = 5,
    ) -> str:
        """Perform a search and return a direct Q&A summary answer (matches Tavily API)."""
        response = self.search(
            query=query,
            search_depth=search_depth,
            max_results=max_results,
            include_answer=True,
        )
        return response.get("answer") or self.get_search_context(query, max_results=2)


# Client alias
Client = TavilyClient


def search(
    query: str,
    search_depth: SearchDepth = "basic",
    max_results: int = 5,
    **kwargs: Any,
) -> SearchResponse:
    """Convenience functional interface for search.

    Example:
        >>> from taviless import search
        >>> results = search("python asyncio event loop")
    """
    client = TavilyClient(**kwargs)
    return client.search(
        query=query,
        search_depth=search_depth,
        max_results=max_results,
    )
