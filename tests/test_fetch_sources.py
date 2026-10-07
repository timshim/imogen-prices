"""Tests for scripts/fetch_sources.py's HTML-to-text conversion (no network).

Run from the repository root: python3 -m unittest discover -s tests
"""
import importlib.util
import os
import unittest

_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts", "fetch_sources.py")
_spec = importlib.util.spec_from_file_location("fetch_sources", _PATH)
fetch_sources = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fetch_sources)

PAGE = """<html><head><title>Pricing</title><style>td { color: red }</style></head><body>
<h1>Model pricing</h1><p>Prices in USD.</p>
<table><tr><th>Model</th><th>Price</th></tr><tr><td>Seedream 5.0</td><td>$0.035 / image</td></tr></table>
<script>window.prices = {"seedance": "$0.15"};</script><noscript>Enable JavaScript</noscript>
</body></html>"""


class HTMLToTextTests(unittest.TestCase):
    def test_keeps_text_and_table_rows(self):
        text = fetch_sources.html_to_text(PAGE)
        self.assertIn("Model pricing", text)
        self.assertIn("Seedream 5.0 | $0.035 / image", text)
        self.assertNotIn("Pricing\n", text.split("Model pricing")[0])  # <head> is left out

    def test_drops_scripts_styles_and_noscript_by_default(self):
        text = fetch_sources.html_to_text(PAGE)
        self.assertNotIn("window.prices", text)
        self.assertNotIn("color: red", text)
        self.assertNotIn("Enable JavaScript", text)

    def test_keeps_script_text_when_asked(self):
        self.assertIn('"seedance": "$0.15"', fetch_sources.html_to_text(PAGE, keep_scripts=True))

    def test_decodes_entities_and_collapses_whitespace(self):
        text = fetch_sources.html_to_text("<p>Fast&nbsp;&amp;   cheap</p><p></p><p>Fast&nbsp;&amp; cheap</p>")
        self.assertEqual(text.replace("\xa0", " "), "Fast & cheap")


if __name__ == "__main__":
    unittest.main()
