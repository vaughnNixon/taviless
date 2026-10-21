"""Base interface and utilities for search engine implementations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional
import urllib.parse

from taviless.types import SearchResult


class BaseSearchEngine(ABC):
    """Abstract base class for all search engines."""

    @abstractmethod
    def search(
        self,
        query: str,
        max_results: int = 5,
        include_domains: Optional[List[str]] = None,
        exclude_domains: Optional[List[str]] = None,
        time_range: Optional[str] = None,
    ) -> List[SearchResult]:
        """Execute a search query and return normalized search results.

        Args:
            query: The search terms.
            max_results: Maximum number of results to return.
            include_domains: Optional list of domains to filter by.
            exclude_domains: Optional list of domains to exclude.
            time_range: Optional time restriction ('day', 'week', 'month', 'year').

        Returns:
            List of SearchResult matching Tavily's schema.
        """
        pass

    @staticmethod
    def _normalize_url(url: str) -> str:
        """Strip tracking parameters and fragments from a URL."""
        try:
            parsed = urllib.parse.urlparse(url)
            # Remove common tracking query params
            query_pairs = urllib.parse.parse_qsl(parsed.query)
            clean_pairs = [
                (k, v)
                for k, v in query_pairs
                if not k.startswith("utm_") and k not in {"fbclid", "gclid", "ref"}
            ]
            clean_query = urllib.parse.urlencode(clean_pairs)
            return urllib.parse.urlunparse(
                (parsed.scheme, parsed.netloc, parsed.path, parsed.params, clean_query, "")
            )
        except Exception:
            return url

    @classmethod
    def filter_and_rank(
        cls,
        results: List[SearchResult],
        max_results: int = 5,
        include_domains: Optional[List[str]] = None,
        exclude_domains: Optional[List[str]] = None,
    ) -> List[SearchResult]:
        """Deduplicate, filter by domain, and cap results."""
        seen_urls = set()
        filtered: List[SearchResult] = []

        norm_include = [d.lower().strip() for d in (include_domains or []) if d.strip()]
        norm_exclude = [d.lower().strip() for d in (exclude_domains or []) if d.strip()]

        for item in results:
            raw_url = item.get("url", "")
            if not raw_url or not raw_url.startswith("http"):
                continue

            clean_url = cls._normalize_url(raw_url)
            if clean_url in seen_urls:
                continue

            try:
                domain = urllib.parse.urlparse(clean_url).netloc.lower()
            except Exception:
                domain = ""

            # Check include_domains
            if norm_include:
                if not any(domain == inc or domain.endswith("." + inc) for inc in norm_include):
                    continue

            # Check exclude_domains
            if norm_exclude:
                if any(domain == exc or domain.endswith("." + exc) for exc in norm_exclude):
                    continue

            seen_urls.add(clean_url)
            item["url"] = clean_url
            filtered.append(item)

            if len(filtered) >= max_results:
                break

        return filtered
