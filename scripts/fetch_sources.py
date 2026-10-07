"""Downloads each provider's official pricing sources (sources.json) and saves them as text in
sources/<provider>.txt, for the weekly check to read.

These are plain downloads with no JavaScript, so a URL only belongs in sources.json if its prices
are in the page's HTML. An entry is a URL, or {"url": …, "scripts": true} to also keep the text of
the page's <script> tags, for pages that carry their prices as data there. A source that can't be
downloaded is recorded as FAILED in the file; it never stops the run.

Run from the repository root: python3 scripts/fetch_sources.py
"""
import json
import os
import re
import subprocess
import sys
import urllib.request
from html.parser import HTMLParser

BLOCKS = {"address", "article", "aside", "blockquote", "br", "dd", "div", "dl", "dt", "figcaption",
          "footer", "h1", "h2", "h3", "h4", "h5", "h6", "header", "hr", "li", "main", "nav", "ol",
          "p", "pre", "section", "table", "tbody", "thead", "tfoot", "tr", "ul"}
CELLS = {"td", "th"}
HIDDEN = {"head", "noscript", "style", "svg", "template"}
USER_AGENT = "Mozilla/5.0 (compatible; imogen-prices price check; +https://github.com/timshim/imogen-prices)"


class _Text(HTMLParser):
    def __init__(self, keep_scripts):
        super().__init__(convert_charrefs=True)
        self.keep_scripts = keep_scripts
        self.parts = []
        self.hidden = 0
        self.in_script = False

    def handle_starttag(self, tag, attrs):
        if tag in HIDDEN:
            self.hidden += 1
        elif tag == "script":
            self.in_script = True
        elif tag in BLOCKS:
            self.parts.append("\n")
        elif tag in CELLS:
            self.parts.append(" | ")

    def handle_endtag(self, tag):
        if tag in HIDDEN:
            self.hidden = max(0, self.hidden - 1)
        elif tag == "script":
            self.in_script = False
            if self.keep_scripts:
                self.parts.append("\n")
        elif tag in BLOCKS:
            self.parts.append("\n")

    def handle_data(self, data):
        if self.hidden:
            return
        if self.in_script:
            if self.keep_scripts:
                self.parts.append(data)
            return
        self.parts.append(data)


def html_to_text(html, keep_scripts=False):
    """The page's visible text, one block per line, table cells separated by " | "."""
    parser = _Text(keep_scripts)
    parser.feed(html)
    parser.close()
    lines = (re.sub(r"[ \t\r\f\v]+", " ", line).strip() for line in "".join(parser.parts).split("\n"))
    out = []
    for line in lines:
        if line.strip(" |") and (not out or line != out[-1]):
            out.append(line)
    return "\n".join(out)


def download(url):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset, errors="replace")
    except Exception:
        # Some servers refuse older TLS stacks; curl usually has a newer one.
        result = subprocess.run(["curl", "-fsSL", "--max-time", "30", "-A", USER_AGENT, url], capture_output=True)
        if result.returncode != 0:
            raise
        return result.stdout.decode("utf-8", errors="replace")


def main():
    with open("sources.json") as file:
        sources = json.load(file)
    os.makedirs("sources", exist_ok=True)
    for provider, entries in sorted(sources.items()):
        sections = []
        for entry in entries:
            url, keep_scripts = (entry, False) if isinstance(entry, str) else (entry["url"], bool(entry.get("scripts")))
            try:
                text = html_to_text(download(url), keep_scripts)
                sections.append(f"=== {url} ===\n{text}")
                print(f"{provider}: {url} ({len(text.split())} words)")
            except Exception as error:  # Any failure is recorded for the check to report.
                sections.append(f"=== {url} ===\nFAILED: {type(error).__name__}: {error}")
                print(f"{provider}: {url} FAILED ({type(error).__name__}: {error})", file=sys.stderr)
        with open(os.path.join("sources", f"{provider}.txt"), "w") as file:
            file.write("\n\n".join(sections) + "\n")


if __name__ == "__main__":
    main()
