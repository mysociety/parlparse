"""
Table detection, formatting, and HTML table cleanup for SP written questions.

Handles:
- Detecting tabular data in newline-delimited text (column count heuristics)
- Converting flat lines into HTML ``<table>`` markup
- Cleaning malformed HTML tables from the API via lxml
- Splitting mixed text into table / non-table segments
"""

from __future__ import annotations

import re
from typing import NamedTuple, Optional

from .cleanup import escape_xml, resolve_entities


class TextSegment(NamedTuple):
    """A segment of text extracted from API answer/question markup."""

    kind: str  # 'text' or 'html_table'
    content: str


# Matches "Table A:", "Table 1:", "Table:", "Table A1:" etc. as a standalone line
TABLE_HEADER_RE = re.compile(r"^Table\s*\w*\s*:$", re.IGNORECASE)

# Lines that terminate a table block
TABLE_TERMINATOR_RE = re.compile(
    r"^(Notes?:|Sources?:|Table\s+\w+\s*:|N\.?B\.?:?\s)", re.IGNORECASE
)


def _is_data_value(s: str) -> bool:
    """Check if a string looks like a numeric / data cell value."""
    s = s.strip()
    if not s:
        return False
    # Common data values: numbers (with commas/decimals), percentages, currency,
    # dashes, asterisks, n/a
    if s in ("-", "*", "N/A", "n/a", "\u2014", "\u2013"):
        return True
    if re.match(r"^[£$€]?\s*[\d,]+(\.\d+)?\s*%?$", s):
        return True
    return False


def detect_table_columns(lines: list[str]) -> Optional[int]:
    """
    Given non-empty lines of potential table data, detect the number of columns
    by trying divisors and scoring how well data cells match numeric patterns.
    Returns the best column count (2–10), or None if no good fit.
    """
    n = len(lines)
    if n < 4:
        return None

    best_score = 0.0
    best_cols = None

    for cols in range(2, min(11, n)):
        if n % cols != 0:
            continue
        rows = n // cols
        if rows < 2:
            continue

        # Score: proportion of data-like values in columns 1+ of data rows (1+)
        data_cells_total = 0
        data_cells_match = 0
        for r in range(1, rows):
            for c in range(1, cols):
                idx = r * cols + c
                data_cells_total += 1
                if _is_data_value(lines[idx]):
                    data_cells_match += 1

        if data_cells_total == 0:
            continue
        score = data_cells_match / data_cells_total
        # Prefer higher score; for ties prefer smaller column count
        if score > best_score or (
            score == best_score and best_cols and cols < best_cols
        ):
            best_score = score
            best_cols = cols

    # Require at least 50% of data cells to look numeric
    if best_cols and best_score >= 0.5:
        return best_cols
    return None


def lines_to_html_table(lines: list[str], cols: int) -> str:
    """Convert flat lines into an HTML table string (rows of ``cols`` cells)."""
    rows = len(lines) // cols

    parts = ["<tr>"]
    for c in range(cols):
        parts.append(f"<th>{escape_xml(lines[c])}</th>")
    parts.append("</tr>")

    for r in range(1, rows):
        parts.append("<tr>")
        for c in range(cols):
            parts.append(f"<td>{escape_xml(lines[r * cols + c])}</td>")
        parts.append("</tr>")

    return "".join(parts)


def clean_html_table(html: str) -> str:
    """
    Clean up an HTML table from the API for valid XML embedding.

    Uses lxml.html to parse the (potentially malformed) HTML, which
    auto-closes unclosed tags and fixes nesting.  Then strips all
    attributes and non-table elements, returning clean XHTML suitable
    for embedding in XML.
    """
    import lxml.html
    from lxml import etree  # type: ignore[import]

    # Resolve HTML entities first
    html = resolve_entities(html)
    # Remove IE conditional comments before parsing (not valid HTML)
    html = re.sub(r"<!\[if [^\]]*\]>", "", html, flags=re.IGNORECASE)
    html = re.sub(r"<!\[endif\]>", "", html, flags=re.IGNORECASE)

    # Parse as HTML fragment — lxml will fix malformed markup
    try:
        doc = lxml.html.fromstring(html)
    except Exception:
        # If parsing fails entirely, fall back to stripping all tags
        return escape_xml(re.sub(r"<[^>]+>", " ", html))

    # Find the <table> element (it may be the root, or nested)
    table_el = doc if doc.tag == "table" else doc.find(".//table")
    if table_el is None:
        return escape_xml(re.sub(r"<[^>]+>", " ", html))

    # Allowed tags in the output
    ALLOWED_TAGS = {
        "table",
        "tr",
        "td",
        "th",
        "thead",
        "tbody",
        "tfoot",
        "caption",
        "col",
        "colgroup",
    }

    def _clean_element(el: etree._Element) -> None:
        """Recursively clean: strip attributes, unwrap non-table elements."""
        # Strip all attributes
        for attr in list(el.attrib):
            del el.attrib[attr]

        for child in list(el):
            if child.tag in ALLOWED_TAGS:
                _clean_element(child)
            else:
                # Unwrap: promote text/children, then remove the element
                prev = child.getprevious()
                parent = child.getparent()
                if parent is None:
                    continue
                text = child.text or ""
                tail = child.tail or ""
                if prev is not None:
                    prev.tail = (prev.tail or "") + text
                else:
                    parent.text = (parent.text or "") + text
                # Move sub-children up
                idx = list(parent).index(child)
                for i, sub in enumerate(list(child)):
                    parent.insert(idx + i, sub)
                # Attach tail to previous sibling or parent
                if child.tail:
                    after = child.getnext()
                    if after is not None:
                        after_prev = after.getprevious()
                        if after_prev is not None:
                            after_prev.tail = (after_prev.tail or "") + tail
                        else:
                            parent.text = (parent.text or "") + tail
                parent.remove(child)

    _clean_element(table_el)

    # Serialize to string
    result = etree.tostring(table_el, encoding="unicode")
    # Escape bare & in text content (not part of XML entities)
    result = re.sub(
        r"&(?!amp;|lt;|gt;|quot;|apos;|#\d+;|#x[\da-fA-F]+;)", "&amp;", result
    )
    # Collapse whitespace in cells
    result = re.sub(r"<(td|th)>\s+", r"<\1>", result, flags=re.IGNORECASE)
    result = re.sub(r"\s+</(td|th)>", r"</\1>", result, flags=re.IGNORECASE)
    return result.strip()


def extract_html_tables(text: str) -> list[TextSegment]:
    """
    Split text into a list of :class:`TextSegment` items whose *kind* is
    ``'html_table'`` or ``'text'``.  Preserves ordering.
    """
    parts: list[TextSegment] = []
    # Match <table...>...</table> blocks (case-insensitive, non-greedy)
    # Also handle unclosed <table> blocks (truncated API data) — match to end
    table_re = re.compile(
        r"(<table[\s>].*?</table>|<table[\s>].*$)",
        re.IGNORECASE | re.DOTALL,
    )
    last_end = 0
    for m in table_re.finditer(text):
        if m.start() > last_end:
            parts.append(TextSegment("text", text[last_end : m.start()]))
        table_html = m.group(1)
        # If unclosed, add a closing tag
        if not re.search(r"</table>\s*$", table_html, re.IGNORECASE):
            table_html += "</table>"
        parts.append(TextSegment("html_table", table_html))
        last_end = m.end()
    if last_end < len(text):
        parts.append(TextSegment("text", text[last_end:]))
    return parts
