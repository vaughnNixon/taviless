"""Main client interface for Taviless, offering 100% drop-in parity with Tavily."""

from __future__ import annotations

import concurrent.futures
import logging
import re
import time
from typing import Any, Dict, List, Optional

from taviless import diagnostics
from taviless.engines import MultiEngineGateway
from taviless.extractor import fetch_and_extract
from taviless.scoring import extractive_answer, score_results
from taviless.types import SearchDepth, SearchResponse, SearchResult

logger = logging.getLogger(__name__)

TEMPORAL_KEYWORDS = re.compile(
    r"\b(latest|recent|newest|today|breaking|upcoming|this month|this week)\b",
    re.IGNORECASE,
)


def _days_to_time_range(days: int) -> str:
    """Map Tavily's `days` window onto the coarse buckets search engines support."""
    if days <= 1:
        return "day"
    if days <= 7:
        return "week"
    if days <= 31:
        return "month"
    return "year"


def _build_engine_query(
    query: str,
    include_domains: Optional[List[str]],
    exclude_domains: Optional[List[str]],
) -> str:
    """Push domain filters into the query itself (site:/-site:) so engines apply
    them *before* ranking, instead of us discarding results afterwards."""
    parts = [query.strip()]
    inc = [d.strip() for d in (include_domains or []) if d and d.strip()]
    exc = [d.strip() for d in (exclude_domains or []) if d and d.strip()]
    if len(inc) == 1:
        parts.append(f"site:{inc[0]}")
    elif inc:
        parts.append("(" + " OR ".join(f"site:{d}" for d in inc) + ")")
    parts.extend(f"-site:{d}" for d in exc)
    return " ".join(parts)


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
        topic: str = "general",
        days: Optional[int] = None,
        **kwargs: Any,
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
            topic: Tavily-compatible ("general", "news", "finance"). "news" implies a
                recency window (default one week) since engines have no news-only mode here.
            days: Tavily-compatible recency window in days; mapped onto `time_range`.
            **kwargs: Other Tavily parameters are accepted for drop-in compatibility
                and ignored (logged at debug level).

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

        diagnostics.begin()

        if kwargs:
            logger.debug("Ignoring unsupported Tavily parameters: %s", sorted(kwargs))

        # Tavily's topic/days -> time_range (explicit time_range always wins)
        if not time_range:
            if days is not None and days > 0:
                time_range = _days_to_time_range(int(days))
            elif topic == "news":
                time_range = "week"

        # Auto-detect temporal intent if time_range wasn't explicitly passed
        is_temporal = bool(time_range) or bool(TEMPORAL_KEYWORDS.search(query))
        effective_time_range = time_range or ("month" if is_temporal else None)

        engine_query = _build_engine_query(query, include_domains, exclude_domains)

        # Step 1: Fetch search engine results
        raw_results = self.gateway.search(
            query=engine_query,
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
                    query=engine_query,
                    max_results=max_results,
                    include_domains=include_domains,
                    exclude_domains=exclude_domains,
                    time_range=None,
                )
            )

        # Heuristic relevance score (rank prior + query-term overlap); sorts results
        results = score_results(query, results)

        # Step 2: Crawl top pages in parallel if advanced depth or if an answer is requested
        max_crawl = kwargs.get("max_chars")
        if search_depth == "advanced" and results:
            results = self._crawl_and_extract_parallel(
                results,
                include_raw_content=include_raw_content,
                reverse_chronological=is_temporal,
                max_chars=max_crawl or 20000,
            )
        elif include_answer and results:
            # When an answer is requested in basic depth, peek at the top 2 results concurrently
            # with clean content so the extractive answer has grounded facts instead of truncated snippets.
            peek_n = min(2, len(results))
            top_peek = self._crawl_and_extract_parallel(
                results[:peek_n],
                include_raw_content=False,
                reverse_chronological=False,
                max_chars=max_crawl or 10000,
            )
            results = top_peek + results[peek_n:]

        elapsed = round(time.time() - start_time, 2)

        # Step 3: Formulate answer if requested
        answer: Optional[str] = None
        if include_answer and results:
            answer = extractive_answer(query, results)

        response: SearchResponse = {
            "query": query,
            "results": results,
            "response_time": elapsed,
            "answer": answer,
            "images": [],
        }
        warnings = diagnostics.collect()
        if warnings:
            response["warnings"] = warnings
            if not results:
                logger.warning("Search returned no results for %r: %s", query, "; ".join(warnings))
        return response

    def _crawl_and_extract_parallel(
        self,
        results: List[SearchResult],
        include_raw_content: bool = False,
        reverse_chronological: bool = False,
        max_chars: int = 20000,
    ) -> List[SearchResult]:
        """Crawl the top links concurrently and extract clean, token-dense markdown content."""

        failed: List[str] = []

        def _fetch_one(item: SearchResult) -> SearchResult:
            url = item.get("url", "")
            if not url:
                return item

            clean_text, raw_html = fetch_and_extract(
                url=url,
                timeout=self.crawl_timeout,
                max_chars=max_chars,
                use_trafilatura=self.use_trafilatura,
                reverse_chronological=reverse_chronological,
            )
            if raw_html is None:
                failed.append(url)

            # If full page content was successfully extracted, replace snippet
            updated = dict(item)
            if clean_text and len(clean_text.strip()) > len(item.get("content", "")):
                updated["content"] = clean_text

            if include_raw_content:
                updated["raw_content"] = raw_html

            return updated  # type: ignore

        workers = min(len(results), self.max_workers)
        if workers <= 1:
            crawled = [_fetch_one(r) for r in results]
        else:
            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
                crawled = list(executor.map(_fetch_one, results))

        if failed:
            diagnostics.note(f"crawl: could not fetch {len(failed)} of {len(results)} pages (kept search snippets)")
        return crawled

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

    def extract(
        self,
        urls: Union[str, List[str]],
        include_images: bool = False,
        extract_depth: str = "basic",
        max_chars: Optional[int] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Extract content from one or more URLs in parallel (Tavily extract API compatible).

        Args:
            urls: A single URL string or a list of URL strings.
            include_images: Whether to extract images (reserved for compatibility).
            extract_depth: "basic" or "advanced".
            max_chars: Optional maximum character count to retain per URL.
            **kwargs: Other Tavily extract arguments (safely ignored).

        Returns:
            Dictionary matching Tavily extract schema:
            {'results': [{'url': ..., 'raw_content': ...}], 'failed_results': [...], 'response_time': ...}
        """
        start_time = time.time()
        url_list = [urls] if isinstance(urls, str) else list(urls)

        results: List[Dict[str, Any]] = []
        failed_results: List[Dict[str, Any]] = []

        effective_max_chars = max_chars or (25000 if extract_depth == "advanced" else 10000)

        def _extract_one(target_url: str):
            try:
                clean_text, raw_html = fetch_and_extract(
                    url=target_url,
                    timeout=self.crawl_timeout,
                    max_chars=effective_max_chars,
                    use_trafilatura=self.use_trafilatura,
                )
                if clean_text:
                    return {"url": target_url, "raw_content": clean_text}, None
                else:
                    return None, {"url": target_url, "error": "No content extracted"}
            except Exception as e:
                return None, {"url": target_url, "error": str(e)}

        workers = min(len(url_list), self.max_workers) or 1
        if workers <= 1:
            extracted_pairs = [_extract_one(u) for u in url_list]
        else:
            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
                extracted_pairs = list(executor.map(_extract_one, url_list))

        for success, failure in extracted_pairs:
            if success:
                results.append(success)
            elif failure:
                failed_results.append(failure)

        elapsed = round(time.time() - start_time, 2)
        return {
            "results": results,
            "failed_results": failed_results,
            "response_time": elapsed,
        }


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
    ctor_keys = {"api_key", "searxng_url", "default_engine", "request_timeout",
                 "crawl_timeout", "max_workers", "use_trafilatura"}
    client = TavilyClient(**{k: v for k, v in kwargs.items() if k in ctor_keys})
    search_kwargs = {k: v for k, v in kwargs.items() if k not in ctor_keys}
    return client.search(
        query=query,
        search_depth=search_depth,
        max_results=max_results,
        **search_kwargs,
    )


def extract(
    urls: Union[str, List[str]],
    **kwargs: Any,
) -> Dict[str, Any]:
    """Convenience functional interface for URL content extraction.

    Example:
        >>> from taviless import extract
        >>> data = extract("https://docs.python.org/3/library/asyncio.html")
    """
    ctor_keys = {"api_key", "searxng_url", "default_engine", "request_timeout",
                 "crawl_timeout", "max_workers", "use_trafilatura"}
    client = TavilyClient(**{k: v for k, v in kwargs.items() if k in ctor_keys})
    extract_kwargs = {k: v for k, v in kwargs.items() if k not in ctor_keys}
    return client.extract(urls=urls, **extract_kwargs)
