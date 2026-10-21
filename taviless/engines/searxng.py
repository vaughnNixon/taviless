"""SearXNG multi-gateway search engine with automatic failover and circuit breaker."""

from __future__ import annotations

import concurrent.futures
import json
import logging
import os
import threading
import time
from typing import Dict, List, Optional
import urllib.parse
import urllib.request

from taviless.engines.base import BaseSearchEngine
from taviless.types import SearchResult

logger = logging.getLogger(__name__)

DEFAULT_PUBLIC_GATEWAYS: List[str] = [
    "https://search.lumy.live",
    "https://priv.au",
    "https://search.ononoki.org",
    "https://searx.be",
    "https://searxng.site",
]

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}


class SearXNGEngine(BaseSearchEngine):
    """SearXNG JSON engine supporting custom instances and dynamic public gateway failover."""

    def __init__(
        self,
        custom_url: Optional[str] = None,
        public_gateways: Optional[List[str]] = None,
        timeout: float = 2.5,
        circuit_cooldown_seconds: float = 300.0,
    ) -> None:
        self.custom_url = custom_url or os.getenv("TAVILESS_SEARXNG_URL") or os.getenv("SEARXNG_URL")
        self.gateways = list(public_gateways or DEFAULT_PUBLIC_GATEWAYS)
        self.timeout = timeout
        self.cooldown = circuit_cooldown_seconds
        # gateway -> last_failure_timestamp
        self._circuit_breakers: Dict[str, float] = {}
        self._lock = threading.Lock()

    def search(
        self,
        query: str,
        max_results: int = 5,
        include_domains: Optional[List[str]] = None,
        exclude_domains: Optional[List[str]] = None,
        time_range: Optional[str] = None,
    ) -> List[SearchResult]:
        """Query SearXNG gateways with automatic failover."""
        # 1. If custom/local URL is set, prioritize it unconditionally
        if self.custom_url:
            results = self._query_instance(
                self.custom_url,
                query,
                max_results * 2,
                time_range=time_range,
            )
            if results:
                return self.filter_and_rank(
                    results,
                    max_results=max_results,
                    include_domains=include_domains,
                    exclude_domains=exclude_domains,
                )

            # Private instance configured: never fall back to public gateways
            # (would leak queries the user meant to keep private).
            return []

        # 2. Race all public gateways that aren't on cooldown; first non-empty wins.
        #    Worst case is ~one timeout instead of one timeout per gateway.
        now = time.time()
        with self._lock:
            candidates = [
                g for g in self.gateways
                if now - self._circuit_breakers.get(g, 0.0) >= self.cooldown
            ]
        if not candidates:
            return []

        executor = concurrent.futures.ThreadPoolExecutor(max_workers=len(candidates))
        futures = {
            executor.submit(
                self._query_instance, g, query, max_results * 2, time_range=time_range
            ): g
            for g in candidates
        }
        winner: Optional[str] = None
        results: List[SearchResult] = []
        try:
            for fut in concurrent.futures.as_completed(futures):
                gateway = futures[fut]
                try:
                    res = fut.result()
                except Exception:  # _query_instance already swallows; be defensive
                    res = []
                if res:
                    winner, results = gateway, res
                    break
                # Finished empty/failed before any winner: put it on cooldown
                with self._lock:
                    self._circuit_breakers[gateway] = time.time()
        finally:
            # Don't block on slower gateways; they finish on their own within `timeout`
            executor.shutdown(wait=False, cancel_futures=True)

        if not winner:
            return []

        # Promote working gateway to the front of the candidate list
        with self._lock:
            if winner in self.gateways:
                self.gateways.remove(winner)
                self.gateways.insert(0, winner)
        return self.filter_and_rank(
            results,
            max_results=max_results,
            include_domains=include_domains,
            exclude_domains=exclude_domains,
        )

    def _query_instance(
        self,
        base_url: str,
        query: str,
        limit: int,
        time_range: Optional[str] = None,
    ) -> List[SearchResult]:
        """Send a JSON search request to a specific SearXNG instance."""
        clean_base = base_url.rstrip("/")
        param_dict = {
            "q": query,
            "format": "json",
            "categories": "general",
        }
        if time_range:
            param_dict["time_range"] = time_range

        params = urllib.parse.urlencode(param_dict)
        url = f"{clean_base}/search?{params}"
        req = urllib.request.Request(url, headers=DEFAULT_HEADERS)

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                if resp.status != 200:
                    return []
                content = resp.read().decode("utf-8", errors="replace")
                data = json.loads(content)
                raw_results = data.get("results", [])
                return self._parse_json_results(raw_results, limit)
        except Exception as e:
            logger.debug("SearXNG instance %s failed: %s", base_url, e)
            return []

    def _parse_json_results(self, raw_results: list, limit: int) -> List[SearchResult]:
        results: List[SearchResult] = []
        for idx, item in enumerate(raw_results):
            if not isinstance(item, dict):
                continue

            url = item.get("url", "")
            title = item.get("title", "")
            content = item.get("content", "") or item.get("snippet", "")

            # Normalized score calculation
            raw_score = item.get("score")
            if isinstance(raw_score, (int, float)) and raw_score > 0:
                score = round(min(1.0, max(0.40, float(raw_score))), 2)
            else:
                score = max(0.40, round(0.98 - (idx * 0.04), 2))

            if url and title:
                results.append(
                    {
                        "title": title,
                        "url": url,
                        "content": content,
                        "score": score,
                        "raw_content": None,
                    }
                )

            if len(results) >= limit:
                break

        return results
