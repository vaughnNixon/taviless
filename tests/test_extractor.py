"""Unit tests for HTML extraction logic."""

from __future__ import annotations

import unittest

from taviless.extractor.stdlib import extract_text_stdlib


class TestExtractor(unittest.TestCase):
    def test_strip_scripts_styles_and_nav(self) -> None:
        raw_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Test Page</title>
            <style>body { color: red; }</style>
            <script>console.log("tracking pixel");</script>
        </head>
        <body>
            <nav><a href="/home">Home</a><a href="/about">About</a></nav>
            <header><h1>Site Header</h1></header>
            <main>
                <h2>Article Title</h2>
                <p>This is the first paragraph with <b>bold text</b> and &amp; entities.</p>
                <ul>
                    <li>Bullet 1</li>
                    <li>Bullet 2</li>
                </ul>
            </main>
            <footer><p>Copyright 2026</p></footer>
        </body>
        </html>
        """
        extracted = extract_text_stdlib(raw_html)

        # Nav, footer, header, script, style should be purged
        self.assertNotIn("console.log", extracted)
        self.assertNotIn("body { color", extracted)
        self.assertNotIn("Site Header", extracted)
        self.assertNotIn("Copyright 2026", extracted)

        # Content should remain
        self.assertIn("## Article Title", extracted)
        self.assertIn("first paragraph with bold text and & entities.", extracted)
        self.assertIn("- Bullet 1", extracted)
        self.assertIn("- Bullet 2", extracted)

    def test_truncation(self) -> None:
        long_text = "<p>" + ("Python is an interpreted, high-level programming language. " * 30) + "</p>"
        extracted = extract_text_stdlib(long_text, max_chars=120)
        self.assertLessEqual(len(extracted), 130)

    def test_empty_or_whitespace_html(self) -> None:
        self.assertEqual(extract_text_stdlib(""), "")
        self.assertEqual(extract_text_stdlib("   \n\t  "), "")

    def test_reverse_chronological_reordering(self) -> None:
        import datetime
        from taviless.extractor.stdlib import reorder_reverse_chronological

        sample_text = (
            "September 22, 2026: Claude Opus 5.5 was released.\n\n"
            "October 7, 2026: Claude Haiku 5.5 was announced.\n\n"
            "September 28, 2026: Claude Sonnet 5.5 launched."
        )

        ref_date = datetime.date(2026, 10, 21)
        reordered = reorder_reverse_chronological(sample_text, reference_date=ref_date)

        sections = reordered.split("\n\n")
        self.assertEqual(len(sections), 3)
        # Oct 7 should be first, then Sep 28, then Sep 22
        self.assertIn("October 7, 2026", sections[0])
        self.assertIn("September 28, 2026", sections[1])
        self.assertIn("September 22, 2026", sections[2])


if __name__ == "__main__":
    unittest.main()
