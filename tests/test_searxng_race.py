import time
import unittest
from unittest import mock

from taviless.engines.searxng import SearXNGEngine

OK = [{"title": "t", "url": "https://ok.example/a", "content": "c", "score": 0.9, "raw_content": None}]


def make(gws, **kw):
    e = SearXNGEngine(public_gateways=gws, **kw)
    e.custom_url = None  # ignore env
    return e


class TestRace(unittest.TestCase):
    def test_fast_winner_beats_slow_failures(self):
        e = make(["https://slow1", "https://slow2", "https://fast"])

        def fake(base, *a, **k):
            if base == "https://fast":
                time.sleep(0.05)
                return OK
            time.sleep(1.0)
            return []

        with mock.patch.object(e, "_query_instance", side_effect=fake):
            t = time.time()
            res = e.search("q")
            elapsed = time.time() - t
        self.assertEqual(res[0]["url"], "https://ok.example/a")
        self.assertLess(elapsed, 0.6)
        self.assertEqual(e.gateways[0], "https://fast")  # promoted

    def test_failed_gateways_go_on_cooldown(self):
        e = make(["https://a", "https://b"])
        with mock.patch.object(e, "_query_instance", return_value=[]) as q:
            self.assertEqual(e.search("q"), [])
            self.assertEqual(q.call_count, 2)
            self.assertEqual(e.search("q"), [])  # both cooling down: no new calls
            self.assertEqual(q.call_count, 2)

    def test_custom_url_never_hits_public(self):
        e = make(["https://public"])
        e.custom_url = "http://private:8080"
        with mock.patch.object(e, "_query_instance", return_value=[]) as q:
            self.assertEqual(e.search("q"), [])
        urls = [c.args[0] for c in q.call_args_list]
        self.assertEqual(urls, ["http://private:8080"])


if __name__ == "__main__":
    unittest.main()
