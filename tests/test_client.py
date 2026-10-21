"""Unit tests for TavilyClient and functional search API."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from taviless.client import TavilyClient, search
from taviless.types import SearchResult


class TestClient(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TavilyClient(api_key="tvly-mock-key")

    @patch("taviless.engines.MultiEngineGateway.search")
    def test_search_basic_schema(self, mock_search) -> None:
        mock_results: list[SearchResult] = [
            {
                "title": "Quantum Computing 101",
                "url": "https://example.com/quantum",
                "content": "Quantum computers use qubits instead of bits.",
                "score": 0.95,
                "raw_content": None,
            }
        ]
        mock_search.return_value = mock_results

        res = self.client.search("quantum computing", search_depth="basic")

        # Tavily schema assertions
        self.assertEqual(res["query"], "quantum computing")
        self.assertIn("results", res)
        self.assertIn("response_time", res)
        self.assertEqual(len(res["results"]), 1)
        item = res["results"][0]
        self.assertEqual(item["title"], "Quantum Computing 101")
        self.assertEqual(item["url"], "https://example.com/quantum")
        self.assertEqual(item["content"], "Quantum computers use qubits instead of bits.")
        # Score is computed by the client (heuristic), always within 0.05-0.99
        self.assertGreaterEqual(item["score"], 0.05)
        self.assertLessEqual(item["score"], 0.99)

    @patch("taviless.client.fetch_and_extract")
    @patch("taviless.engines.MultiEngineGateway.search")
    def test_search_advanced_crawling(self, mock_search, mock_fetch) -> None:
        mock_search.return_value = [
            {
                "title": "Deep Article",
                "url": "https://example.com/deep",
                "content": "Short snippet",
                "score": 0.9,
                "raw_content": None,
            }
        ]
        mock_fetch.return_value = (
            "Extensive extracted article body text that is much longer than the snippet.",
            "<html><body>...</body></html>",
        )

        res = self.client.search(
            "deep tech",
            search_depth="advanced",
            include_raw_content=True,
        )

        self.assertEqual(len(res["results"]), 1)
        item = res["results"][0]
        self.assertIn("Extensive extracted article body text", item["content"])
        self.assertEqual(item["raw_content"], "<html><body>...</body></html>")

    @patch("taviless.engines.MultiEngineGateway.search")
    def test_get_search_context(self, mock_search) -> None:
        mock_search.return_value = [
            {
                "title": "Doc",
                "url": "https://example.com/doc",
                "content": "Context information for LLM.",
                "score": 0.9,
            }
        ]

        context = self.client.get_search_context("doc query", max_tokens=100)
        self.assertIn("Source: https://example.com/doc", context)
        self.assertIn("Content: Context information for LLM.", context)

    @patch("taviless.engines.MultiEngineGateway.search")
    def test_qna_search(self, mock_search) -> None:
        mock_search.return_value = [
            {
                "title": "Answer Page",
                "url": "https://example.com/ans",
                "content": "Paris is the capital of France.",
                "score": 0.98,
            }
        ]

        ans = self.client.qna_search("capital of France")
        self.assertIn("Paris is the capital of France", ans)

    @patch("taviless.client.fetch_and_extract")
    def test_extract(self, mock_fetch) -> None:
        mock_fetch.return_value = ("Clean page body text", "<html>raw</html>")
        res = self.client.extract("https://example.com/article")
        self.assertEqual(len(res["results"]), 1)
        self.assertEqual(res["results"][0]["url"], "https://example.com/article")
        self.assertEqual(res["results"][0]["raw_content"], "Clean page body text")
        self.assertEqual(res["failed_results"], [])
        self.assertIn("response_time", res)


if __name__ == "__main__":
    unittest.main()
