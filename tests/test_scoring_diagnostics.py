import unittest
from unittest import mock
import urllib.error

from taviless import diagnostics
from taviless.client import TavilyClient
from taviless.engines.searxng import SearXNGEngine
from taviless.scoring import extractive_answer, query_terms, score_results


def R(title, url, content, score=0.5):
    return {"title": title, "url": url, "content": content, "score": score, "raw_content": None}


class TestScoring(unittest.TestCase):
    def test_query_terms_strip_operators_and_stopwords(self):
        self.assertEqual(query_terms("what is the asyncio event loop site:python.org -site:spam.com"),
                         {"asyncio", "event", "loop"})

    def test_relevant_result_outranks_irrelevant_first_hit(self):
        res = [
            R("Cooking pasta", "https://food.example/p", "Boil water and add salt."),
            R("asyncio event loop guide", "https://docs.python.org/asyncio", "The asyncio event loop runs tasks."),
        ]
        out = score_results("asyncio event loop", res)
        self.assertEqual(out[0]["url"], "https://docs.python.org/asyncio")
        scores = [r["score"] for r in out]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertTrue(all(0.05 <= s <= 0.99 for s in scores))

    def test_not_purely_positional(self):
        res = [R(f"t{i}", f"https://a.com/{i}", "nothing relevant") for i in range(4)]
        out = score_results("zebra quantum", res)
        self.assertLess(out[-1]["score"], out[0]["score"])  # decays with rank, but computed


class TestExtractiveAnswer(unittest.TestCase):
    def test_returns_matching_sentence_with_source(self):
        res = [R("t", "https://www.docs.python.org/x",
                 "Intro text here that is long enough to be a sentence by length. "
                 "The asyncio event loop is the core of every asyncio application and runs tasks.")]
        ans = extractive_answer("what is the asyncio event loop", res)
        self.assertIn("event loop is the core", ans)
        self.assertIn("docs.python.org", ans)
        self.assertNotIn("www.", ans)

    def test_none_when_no_overlap(self):
        res = [R("t", "https://a.com", "Completely unrelated content about gardening and soil health tips.")]
        self.assertIsNone(extractive_answer("quantum entanglement experiments", res))

    def test_client_include_answer_none_when_unconfident(self):
        c = TavilyClient()
        c.gateway = mock.Mock()
        c.gateway.search.return_value = [R("t", "https://a.com", "Gardening and soil health tips for spring.")]
        resp = c.search("quantum entanglement", include_answer=True)
        self.assertIsNone(resp["answer"])


class TestDiagnostics(unittest.TestCase):
    def test_warnings_surface_when_engines_fail(self):
        c = TavilyClient(default_engine="duckduckgo")
        with mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("boom")):
            resp = c.search("anything")
        self.assertEqual(resp["results"], [])
        self.assertTrue(any("duckduckgo" in w and "boom" in w for w in resp["warnings"]))

    def test_no_warnings_key_when_healthy(self):
        c = TavilyClient()
        c.gateway = mock.Mock()
        c.gateway.search.return_value = [R("t", "https://a.com", "content")]
        self.assertNotIn("warnings", c.search("x"))

    def test_searxng_errors_noted_when_all_gateways_fail(self):
        e = SearXNGEngine(public_gateways=["https://a", "https://b"])
        e.custom_url = None

        def fake(base, *a, errors=None, **k):
            errors.append(f"searxng {base}: HTTP 403")
            return []

        diagnostics.begin()
        with mock.patch.object(e, "_query_instance", side_effect=fake):
            self.assertEqual(e.search("q"), [])
        msgs = diagnostics.collect()
        self.assertEqual(len(msgs), 2)
        self.assertTrue(all("403" in m for m in msgs))

    def test_thread_local_isolation(self):
        import threading
        diagnostics.begin()
        diagnostics.note("main")
        seen = []
        t = threading.Thread(target=lambda: seen.append(diagnostics.collect()))
        t.start(); t.join()
        self.assertEqual(seen, [[]])
        self.assertEqual(diagnostics.collect(), ["main"])


if __name__ == "__main__":
    unittest.main()
