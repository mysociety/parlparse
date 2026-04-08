"""
Convert Scottish Parliament API text into SpeechItem sequences.

Orchestrates the cleanup (see cleanup module) and table handling
(see tables module) modules to turn raw API question/answer text
into lists of SpeechItem objects ready for transcript assembly.
"""

from __future__ import annotations

import re
from typing import Optional

from mysoc_validator.models.transcripts import SpeechItem
from mysoc_validator.models.xml_base import MixedContentHolder

from .cleanup import escape_xml, resolve_entities, strip_html_tags
from .tables import (
    TABLE_HEADER_RE,
    TABLE_TERMINATOR_RE,
    clean_html_table,
    detect_table_columns,
    extract_html_tables,
    lines_to_html_table,
)


def _text_block_to_speech_items(
    text: str, qnum: Optional[str] = None
) -> list[SpeechItem]:
    """
    Convert a block of plain text (no HTML tables) into SpeechItems.
    Detects "Table X:" headers and converts the following newline-delimited
    data into HTML tables.  Other text is split into <p> elements at
    paragraph boundaries (blank lines).
    """
    # Strip any residual HTML tags that aren't part of a table block
    text = strip_html_tags(text)
    text = text.strip()
    if not text:
        return []

    lines = [ln.strip() for ln in text.replace("\r\n", "\n").split("\n")]
    items: list[SpeechItem] = []

    i = 0
    para_lines: list[str] = []  # accumulator for the current paragraph

    def flush_para() -> None:
        """Emit the accumulated paragraph lines as a <p> SpeechItem."""
        nonlocal para_lines
        joined = " ".join(para_lines).strip()
        if joined:
            safe = escape_xml(joined)
            safe = re.sub(r"  +", " ", safe)
            items.append(
                SpeechItem(
                    tag="p",
                    qnum=qnum if not items else None,
                    content=MixedContentHolder(text=safe, raw=safe),
                )
            )
        para_lines = []

    while i < len(lines):
        line = lines[i]

        # Blank line → paragraph break
        if not line:
            flush_para()
            i += 1
            continue

        # "Table X:" header → try to build an HTML table from following lines
        if TABLE_HEADER_RE.match(line):
            flush_para()
            # Emit the "Table X:" line itself as a <p>
            header_safe = escape_xml(line)
            items.append(
                SpeechItem(
                    tag="p",
                    content=MixedContentHolder(text=header_safe, raw=header_safe),
                )
            )
            i += 1

            # Collect non-empty lines until a terminator
            table_lines: list[str] = []
            while i < len(lines):
                tl = lines[i]
                if not tl:
                    i += 1
                    continue  # skip blank lines within table data
                if TABLE_TERMINATOR_RE.match(tl):
                    break  # stop — this line belongs to the next block
                table_lines.append(tl)
                i += 1

            if table_lines:
                cols = detect_table_columns(table_lines)
                if cols:
                    table_html = lines_to_html_table(table_lines, cols)
                    plain = " ".join(table_lines)
                    items.append(
                        SpeechItem(
                            tag="table",
                            content=MixedContentHolder(text=plain, raw=table_html),
                        )
                    )
                else:
                    # Could not detect columns — fall back to <p> per line
                    for tl in table_lines:
                        safe = escape_xml(tl)
                        items.append(
                            SpeechItem(
                                tag="p",
                                content=MixedContentHolder(text=safe, raw=safe),
                            )
                        )
            continue

        # Normal text line
        para_lines.append(line)
        i += 1

    flush_para()
    return items


def text_to_speech_items(text: str, qnum: Optional[str] = None) -> list[SpeechItem]:
    """
    Convert API answer/question text into a list of SpeechItems.

    Handles:
    - HTML ``<table>`` blocks (passed through, cleaned via lxml)
    - "Table X:" headers followed by newline-delimited data (auto-detected columns)
    - Multi-paragraph text (split into separate ``<p>`` elements)
    """
    text = text.strip()
    if not text:
        safe = escape_xml(text)
        return [
            SpeechItem(
                tag="p",
                qnum=qnum,
                content=MixedContentHolder(text=safe, raw=safe),
            )
        ]

    # First resolve HTML entities throughout
    text = resolve_entities(text)

    # Split out any inline HTML <table> blocks
    parts = extract_html_tables(text)

    all_items: list[SpeechItem] = []
    for segment in parts:
        if segment.kind == "html_table":
            # Clean and normalise the HTML table markup
            cleaned = clean_html_table(segment.content)
            # Strip outer <table>...</table> tags since SpeechItem(tag="table")
            # will re-wrap the content
            inner = re.sub(r"^\s*<table>\s*", "", cleaned, flags=re.IGNORECASE)
            inner = re.sub(r"\s*</table>\s*$", "", inner, flags=re.IGNORECASE)
            # Plain text version
            plain = re.sub(r"<[^>]+>", " ", cleaned)
            plain = re.sub(r"\s+", " ", plain).strip()
            all_items.append(
                SpeechItem(
                    tag="table",
                    content=MixedContentHolder(text=plain, raw=inner),
                )
            )
        else:
            block_items = _text_block_to_speech_items(segment.content, qnum=qnum)
            # Only the very first item across all blocks gets qnum
            if all_items and block_items:
                block_items[0] = SpeechItem(
                    tag=block_items[0].tag,
                    content=block_items[0].content,
                )
            all_items.extend(block_items)

    # Ensure at least one item with qnum
    if not all_items:
        safe = escape_xml(text)
        all_items.append(
            SpeechItem(
                tag="p",
                qnum=qnum,
                content=MixedContentHolder(text=safe, raw=safe),
            )
        )
    elif qnum and not any(it.qnum for it in all_items):
        all_items[0] = SpeechItem(
            tag=all_items[0].tag,
            qnum=qnum,
            content=all_items[0].content,
        )

    return all_items
