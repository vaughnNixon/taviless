import unittest
from unittest import mock

from taviless.client import TavilyClient, _build_engine_query, _days_to_time_range
from taviless import search as module_search


class TestTavilyCompat(unittest.TestCase):
    def _client(self):
        c = TavilyClient()
        c.gateway = mock.Mock()
        c.gateway.search.return_value = [
            {"title": "t", "url": "https://a.com/x", "content": "c", "score": 0.9, "raw_content": None}
        ]
        return c

    def test_engine_query_domains(self):
        self.assertEqual(_build_engine_query("py", ["python.org"], None), "py site:python.org")
        self.assertEqual(
            _build_engine_query("py", ["a.com", "b.com"], ["spam.com"]),
            "py (site:a.com OR site:b.com) -site:spam.com",
        )
        self.assertEqual(_build_engine_query("  py ", None, None), "py")

    def test_days_mapping(self):
        self.assertEqual([_days_to_time_range(d) for d in (1, 3, 20, 90)], ["day", "week", "month", "year"])

    def test_topic_news_sets_week(self):
        c = self._client()
        c.search("election results", topic="news")
        self.assertEqual(c.gateway.search.call_args.kwargs["time_range"], "week")

    def test_days_and_explicit_time_range(self):
        c = self._client()
        c.search("x", days=30)
        self.assertEqual(c.gateway.search.call_args.kwargs["time_range"], "month")
        c.search("x", days=30, time_range="day")
        self.assertEqual(c.gateway.search.call_args.kwargs["time_range"], "day")

    def test_unknown_kwargs_ignored(self):
        c = self._client()
        resp = c.search("x", include_image_descriptions=True, chunks_per_source=3)
        self.assertEqual(len(resp["results"]), 1)

    def test_domains_pushed_into_query(self):
        c = self._client()
        c.search("asyncio", include_domains=["python.org"])
        self.assertIn("site:python.org", c.gateway.search.call_args.kwargs["query"])

    def test_module_search_routes_kwargs(self):
        with mock.patch("taviless.client.TavilyClient.search", return_value={"results": []}) as s:
            module_search("x", topic="news", searxng_url="http://localhost:8080")
            self.assertEqual(s.call_args.kwargs["topic"], "news")


if __name__ == "__main__":
    unittest.main()
