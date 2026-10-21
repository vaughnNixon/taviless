"""Zero-dependency HTML to clean text/Markdown extractor using standard library html.parser."""

from __future__ import annotations

from html.parser import HTMLParser
import html
import re
from typing import List, Set


class _ContentHTMLParser(HTMLParser):
    """A streaming HTML parser that strips noise and formats structural text into Markdown."""

    IGNORABLE_TAGS: Set[str] = {
        "script",
        "style",
        "noscript",
        "svg",
        "nav",
        "footer",
        "header",
        "aside",
        "form",
        "iframe",
        "button",
        "select",
        "option",
        "canvas",
        "video",
        "audio",
        "dialog",
        "menu",
    }

    BLOCK_TAGS: Set[str] = {
        "p",
        "div",
        "article",
        "section",
        "main",
        "blockquote",
        "hr",
        "tr",
    }

    HEADING_TAGS: Set[str] = {"h1", "h2", "h3", "h4", "h5", "h6"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.output: List[str] = []
        self._ignore_stack: List[str] = []
        self._current_tag: str = ""

    def handle_starttag(self, tag: str, attrs: list) -> None:
        tag_lower = tag.lower()
        if tag_lower in self.IGNORABLE_TAGS:
            self._ignore_stack.append(tag_lower)
            return

        if self._ignore_stack:
            return

        self._current_tag = tag_lower

        if tag_lower in self.HEADING_TAGS:
            level = tag_lower[1]
            self.output.append(f"\n\n{'#' * int(level)} ")
        elif tag_lower == "li":
            self.output.append("\n- ")
        elif tag_lower == "br":
            self.output.append("\n")
        elif tag_lower in self.BLOCK_TAGS:
            self.output.append("\n\n")
        elif tag_lower == "blockquote":
            self.output.append("\n\n> ")
        elif tag_lower in ("pre", "code"):
            self.output.append(" `")

    def handle_endtag(self, tag: str) -> None:
        tag_lower = tag.lower()
        if self._ignore_stack and self._ignore_stack[-1] == tag_lower:
            self._ignore_stack.pop()
            return

        if self._ignore_stack:
            return

        if tag_lower in self.BLOCK_TAGS or tag_lower in self.HEADING_TAGS:
            self.output.append("\n")
        elif tag_lower in ("pre", "code"):
            self.output.append("` ")

    def handle_data(self, data: str) -> None:
        if self._ignore_stack:
            return
        if data:
            self.output.append(data)

    def get_text(self) -> str:
        raw_text = "".join(self.output)
        # Unescape any lingering HTML entities
        text = html.unescape(raw_text)

        # Normalize line endings
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        # Replace excessive whitespace on lines while keeping indentation
        lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]

        # Remove duplicate consecutive blank lines
        cleaned_lines: List[str] = []
        blank_counter = 0
        for line in lines:
            if not line:
                blank_counter += 1
                if blank_counter <= 2:
                    cleaned_lines.append("")
            else:
                blank_counter = 0
                cleaned_lines.append(line)

        return "\n".join(cleaned_lines).strip()


def extract_text_stdlib(html_content: str, max_chars: int = 5000) -> str:
    """Extract clean, structural text/markdown from raw HTML using standard library tools.

    Args:
        html_content: Raw HTML document string.
        max_chars: Maximum characters to retain (cuts at nearest sentence or newline).

    Returns:
        Clean, ad-free text formatted with markdown headings and lists.
    """
    if not html_content or not html_content.strip():
        return ""

    parser = _ContentHTMLParser()
    try:
        parser.feed(html_content)
        parser.close()
        text = parser.get_text()
    except Exception:
        # Fallback to pure regex if HTML is severely malformed
        text = re.sub(r"(?is)<(script|style|nav|footer|header).*?>.*?</\1>", " ", html_content)
        text = re.sub(r"<[^>]+>", " ", text)
        text = html.unescape(text)
        text = re.sub(r"\s+", " ", text).strip()

    if max_chars and len(text) > max_chars:
        # Truncate cleanly at a sentence break if possible
        truncated = text[:max_chars]
        last_punct = max(truncated.rfind(". "), truncated.rfind(".\n"), truncated.rfind("\n"))
        if last_punct > max_chars * 0.7:
            text = truncated[: last_punct + 1].strip()
        else:
            text = truncated.rstrip() + "..."

    return text


MONTHS = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3,
    "april": 4, "apr": 4, "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7,
    "august": 8, "aug": 8, "september": 9, "sep": 9, "sept": 9, "october": 10,
    "oct": 10, "november": 11, "nov": 11, "december": 12, "dec": 12
}

MONTH_REGEX = r'(?:' + '|'.join(sorted(MONTHS.keys(), key=len, reverse=True)) + r')'


def extract_dates_from_text(text: str) -> List["datetime.date"]:
    """Find calendar dates in text string."""
    import datetime
    found: List[datetime.date] = []

    # Pattern 1: Month Day, Year (e.g. October 7, 2026 or Oct 7 2026)
    for m in re.finditer(rf'({MONTH_REGEX})\s*(\d{{1,2}})(?:st|nd|rd|th)?,?\s*(\d{{4}})\b', text, re.I):
        mon_str, day_str, year_str = m.group(1).lower(), m.group(2), m.group(3)
        try:
            d = datetime.date(int(year_str), MONTHS[mon_str], int(day_str))
            found.append(d)
        except ValueError:
            pass

    # Pattern 2: Day Month Year (e.g. 7 October 2026)
    for m in re.finditer(rf'\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({MONTH_REGEX}),?\s*(\d{{4}})\b', text, re.I):
        day_str, mon_str, year_str = m.group(1), m.group(2).lower(), m.group(3)
        try:
            d = datetime.date(int(year_str), MONTHS[mon_str], int(day_str))
            found.append(d)
        except ValueError:
            pass

    # Pattern 3: ISO YYYY-MM-DD
    for m in re.finditer(r'\b(\d{4})-(\d{2})-(\d{2})\b', text):
        y, mo, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            d = datetime.date(y, mo, day)
            found.append(d)
        except ValueError:
            pass

    return found


def reorder_reverse_chronological(text: str, reference_date: Any = None) -> str:
    """Sort text sections reverse-chronologically based on detected timestamps <= reference_date.

    Places the freshest, most recently dated paragraphs at the very top.
    """
    import datetime
    if not text or not text.strip():
        return text

    today = reference_date or datetime.date.today()
    raw = [s.strip() for s in text.split("\n\n") if s.strip()]
    # Keep each heading attached to the paragraph that follows it
    sections: List[str] = []
    i = 0
    while i < len(raw):
        if raw[i].startswith("#") and i + 1 < len(raw):
            sections.append(raw[i] + "\n\n" + raw[i + 1])
            i += 2
        else:
            sections.append(raw[i])
            i += 1
    if len(sections) <= 1:
        return text

    dated_sections = []
    undated_sections = []

    for s in sections:
        dates = [d for d in extract_dates_from_text(s) if d <= today]
        if dates:
            latest_d = max(dates)
            dated_sections.append((latest_d, s))
        else:
            undated_sections.append(s)

    # Only reorder content that is mostly dated entries (changelogs, news feeds);
    # reordering ordinary prose destroys its structure.
    if len(dated_sections) < 3 or len(dated_sections) * 2 < len(sections):
        return text

    # Sort dated sections with newest date first (descending)
    dated_sections.sort(key=lambda x: x[0], reverse=True)
    sorted_dated = [s for _, s in dated_sections]

    # Combine freshest dated sections first, followed by general undated background
    return "\n\n".join(sorted_dated + undated_sections)

