"""Zero-dependency DuckDuckGo search engine using standard library urllib and HTML parsing."""

from __future__ import annotations

from html.parser import HTMLParser
import html
import logging
import random
import re
from typing import List, Optional
import urllib.parse
import urllib.request

from taviless.engines.base import BaseSearchEngine
from taviless.types import SearchResult

logger = logging.getLogger(__name__)

USER_AGENTS = [
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/129.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/17.4 Safari/605.1.15"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/128.0.0.0 Edge/128.0.0.0"
    ),
]


def _clean_ddg_url(raw_href: str) -> str:
    """Decode real destination URL from DuckDuckGo redirect link."""
    if not raw_href:
        return ""
    if raw_href.startswith("//"):
        raw_href = "https:" + raw_href
    elif raw_href.startswith("/"):
        raw_href = "https://duckduckgo.com" + raw_href

    parsed = urllib.parse.urlparse(raw_href)
    if "duckduckgo.com" in parsed.netloc and "/l/" in parsed.path:
        query_dict = urllib.parse.parse_qs(parsed.query)
        if "uddg" in query_dict and query_dict["uddg"]:
            return query_dict["uddg"][0]

    return raw_href


def _strip_html_tags(text: str) -> str:
    """Strip all HTML tags and unescape HTML entities."""
    clean = re.sub(r"<[^>]+>", "", text)
    return html.unescape(clean).strip()


class DuckDuckGoEngine(BaseSearchEngine):
    """DuckDuckGo scraper providing high-reliability, zero-dependency search."""

    def __init__(self, timeout: float = 5.0) -> None:
        self.timeout = timeout

    def _get_headers(self) -> dict:
        ua = random.choice(USER_AGENTS)
        return {
            "User-Agent": ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

    def search(
        self,
        query: str,
        max_results: int = 5,
        include_domains: Optional[List[str]] = None,
        exclude_domains: Optional[List[str]] = None,
        time_range: Optional[str] = None,
    ) -> List[SearchResult]:
        """Perform DuckDuckGo search via GET html, POST html, or lite endpoints."""
        df_code = self._map_time_range(time_range)

        # Try GET request first (most resilient against bot challenges)
        results = self._search_html_get(query, max_results * 2, df_code=df_code)
        if not results:
            # Fallback to POST request
            results = self._search_html_post(query, max_results * 2, df_code=df_code)
        if not results:
            # Fallback to lite endpoint
            results = self._search_lite(query, max_results * 2, df_code=df_code)

        return self.filter_and_rank(
            results,
            max_results=max_results,
            include_domains=include_domains,
            exclude_domains=exclude_domains,
        )

    @staticmethod
    def _map_time_range(time_range: Optional[str]) -> Optional[str]:
        if not time_range:
            return None
        mapping = {
            "day": "d",
            "d": "d",
            "week": "w",
            "w": "w",
            "month": "m",
            "m": "m",
            "year": "y",
            "y": "y",
        }
        return mapping.get(time_range.lower())

    def _search_html_get(self, query: str, limit: int, df_code: Optional[str] = None) -> List[SearchResult]:
        """Query html.duckduckgo.com/html/?q= via HTTP GET."""
        params = {"q": query}
        if df_code:
            params["df"] = df_code
        encoded = urllib.parse.urlencode(params)
        url = f"https://html.duckduckgo.com/html/?{encoded}"
        req = urllib.request.Request(url, headers=self._get_headers())

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                if resp.status == 200:
                    body = resp.read().decode("utf-8", errors="replace")
                    if "web-result" in body:
                        return self._parse_html_results(body, limit)
            return []
        except Exception as e:
            logger.debug("DuckDuckGo HTML GET search failed: %s", e)
            return []

    def _search_html_post(self, query: str, limit: int, df_code: Optional[str] = None) -> List[SearchResult]:
        """Query html.duckduckgo.com/html/ via HTTP POST."""
        url = "https://html.duckduckgo.com/html/"
        params = {"q": query}
        if df_code:
            params["df"] = df_code
        data = urllib.parse.urlencode(params).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=self._get_headers())

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                if resp.status == 200:
                    body = resp.read().decode("utf-8", errors="replace")
                    if "web-result" in body:
                        return self._parse_html_results(body, limit)
            return []
        except Exception as e:
            logger.debug("DuckDuckGo HTML POST search failed: %s", e)
            return []

    def _parse_html_results(self, html_doc: str, limit: int) -> List[SearchResult]:
        results: List[SearchResult] = []
        # Find all web result blocks
        blocks = re.findall(
            r'<div class="[^"]*web-result[^"]*">([\s\S]*?)<div class="clear"></div>',
            html_doc,
        )

        for idx, block in enumerate(blocks):
            # Extract title and URL
            title_match = re.search(
                r'<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"[^>]*>([\s\S]*?)</a>',
                block,
            )
            if not title_match:
                continue

            raw_url = title_match.group(1)
            raw_title = title_match.group(2)
            url = _clean_ddg_url(raw_url)
            title = _strip_html_tags(raw_title)

            # Extract snippet
            snippet_match = re.search(
                r'<a[^>]+class="[^"]*result__snippet[^"]*"[^>]*>([\s\S]*?)</a>',
                block,
            )
            snippet = _strip_html_tags(snippet_match.group(1)) if snippet_match else ""

            # Score decays slightly down the list
            score = max(0.40, round(0.98 - (idx * 0.04), 2))

            if url and title:
                results.append(
                    {
                        "title": title,
                        "url": url,
                        "content": snippet,
                        "score": score,
                        "raw_content": None,
                    }
                )

            if len(results) >= limit:
                break

        return results

    def _search_lite(self, query: str, limit: int, df_code: Optional[str] = None) -> List[SearchResult]:
        """Fallback to lite.duckduckgo.com/lite/."""
        params = {"q": query}
        if df_code:
            params["df"] = df_code
        encoded = urllib.parse.urlencode(params)
        url = f"https://lite.duckduckgo.com/lite/?{encoded}"
        req = urllib.request.Request(url, headers=self._get_headers())

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                if resp.status == 200:
                    body = resp.read().decode("utf-8", errors="replace")
                    return self._parse_lite_results(body, limit)
            return []
        except Exception as e:
            logger.debug("DuckDuckGo Lite search failed: %s", e)
            return []

    def _parse_lite_results(self, html_doc: str, limit: int) -> List[SearchResult]:
        results: List[SearchResult] = []
        link_matches = re.findall(
            r'<a[^>]+class="result-link"[^>]+href="([^"]+)"[^>]*>([\s\S]*?)</a>',
            html_doc,
        )
        snippet_matches = re.findall(
            r'<td class="result-snippet"[^>]*>([\s\S]*?)</td>',
            html_doc,
        )

        for idx, (raw_url, raw_title) in enumerate(link_matches):
            url = _clean_ddg_url(raw_url)
            title = _strip_html_tags(raw_title)
            snippet = (
                _strip_html_tags(snippet_matches[idx])
                if idx < len(snippet_matches)
                else ""
            )
            score = max(0.40, round(0.98 - (idx * 0.04), 2))

            if url and title:
                results.append(
                    {
                        "title": title,
                        "url": url,
                        "content": snippet,
                        "score": score,
                        "raw_content": None,
                    }
                )
            if len(results) >= limit:
                break

        return results
