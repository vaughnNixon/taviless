import unittest
from taviless.engines.base import BaseSearchEngine as B
from taviless.client import TEMPORAL_KEYWORDS as T
from taviless.extractor.stdlib import reorder_reverse_chronological as reorder
from taviless.extractor import _is_public_url


class Regressions(unittest.TestCase):
    def test_url_not_rewritten(self):
        url = "https://github.com/x/y?ref=main&a=&b=1"
        out = B.filter_and_rank([{"url": url, "title": "t"}])
        self.assertEqual(out[0]["url"], url)

    def test_dedup_ignores_tracking(self):
        r = [{"url": "https://a.com/p?utm_x=1"}, {"url": "https://a.com/p"}]
        self.assertEqual(len(B.filter_and_rank(r)), 1)

    def test_temporal_false_positives(self):
        self.assertFalse(T.search("create a new file in python"))
        self.assertFalse(T.search("history of New York"))
        self.assertTrue(T.search("latest python release"))

    def test_reorder_keeps_prose(self):
        text = "## Intro\n\nSome prose\n\nMore prose\n\nJanuary 2, 2026 did Y"
        self.assertEqual(reorder(text), text)

    def test_reorder_changelog(self):
        text = "January 2, 2026 a\n\nOctober 7, 2026 b\n\nMarch 3, 2026 c"
        self.assertTrue(reorder(text).startswith("October 7, 2026"))

    def test_ssrf_guard(self):
        for u in ("http://127.0.0.1/", "http://localhost/", "http://169.254.169.254/", "file:///etc/passwd"):
            self.assertFalse(_is_public_url(u), u)


if __name__ == "__main__":
    unittest.main()
