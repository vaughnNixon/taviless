"""Unit tests for search engines and gateway routing."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from taviless.engines.base import BaseSearchEngine
from taviless.engines.duckduckgo import DuckDuckGoEngine
from taviless.engines.searxng import SearXNGEngine
from taviless.types import SearchResult


class TestEngines(unittest.TestCase):
    def test_url_normalization_and_filtering(self) -> None:
        sample_results: list[SearchResult] = [
            {
                "title": "Python Docs",
                "url": "https://docs.python.org/3/library/asyncio.html?utm_source=test&ref=123",
                "content": "Asyncio docs",
                "score": 0.9,
            },
            {
                "title": "Duplicate URL",
                "url": "https://docs.python.org/3/library/asyncio.html",
                "content": "Duplicate",
                "score": 0.8,
            },
            {
                "title": "Bad Domain",
                "url": "https://spam.com/article",
                "content": "Spam",
                "score": 0.7,
            },
            {
                "title": "Valid Blog",
                "url": "https://blog.python.org/news",
                "content": "Python blog",
                "score": 0.6,
            },
        ]

        filtered = BaseSearchEngine.filter_and_rank(
            sample_results,
            max_results=5,
            include_domains=["python.org"],
            exclude_domains=["spam.com"],
        )

        # Deduplication check
        self.assertEqual(len(filtered), 2)
        self.assertEqual(filtered[0]["url"], "https://docs.python.org/3/library/asyncio.html")
        self.assertEqual(filtered[1]["url"], "https://blog.python.org/news")

    def test_duckduckgo_html_parser(self) -> None:
        mock_html = """
        <div class="result results_links results_links_deep web-result ">
            <div class="links_main links_deep result__body">
                <h2 class="result__title">
                    <a class="result__a" href="https://example.com/learn-python">Learn Python Tutorial</a>
                </h2>
                <a class="result__snippet" href="https://example.com/learn-python">Comprehensive guide to Python.</a>
                <div class="clear"></div>
            </div>
        </div>
        """
        engine = DuckDuckGoEngine()
        results = engine._parse_html_results(mock_html, limit=5)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "Learn Python Tutorial")
        self.assertEqual(results[0]["url"], "https://example.com/learn-python")
        self.assertEqual(results[0]["content"], "Comprehensive guide to Python.")
        self.assertGreaterEqual(results[0]["score"], 0.9)

    def test_searxng_json_parser(self) -> None:
        raw_results = [
            {
                "title": "SearXNG Article",
                "url": "https://searx.org/item",
                "content": "Snippet from SearXNG",
                "score": 1.5,
            }
        ]
        engine = SearXNGEngine()
        parsed = engine._parse_json_results(raw_results, limit=5)

        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["title"], "SearXNG Article")
        self.assertEqual(parsed[0]["url"], "https://searx.org/item")
        # Score should be normalized between 0.4 and 1.0
        self.assertLessEqual(parsed[0]["score"], 1.0)
        self.assertGreaterEqual(parsed[0]["score"], 0.4)


if __name__ == "__main__":
    unittest.main()
