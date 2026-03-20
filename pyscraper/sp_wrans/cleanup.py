"""
Low-level text cleanup helpers for Scottish Parliament written questions.

Handles HTML entity resolution, XML escaping, and whitespace normalisation.
"""

from __future__ import annotations

import re

HTML_ENTITY_MAP = {
    "&nbsp;": " ",
    "&ndash;": "\u2013",
    "&mdash;": "\u2014",
    "&lsquo;": "\u2018",
    "&rsquo;": "\u2019",
    "&ldquo;": "\u201c",
    "&rdquo;": "\u201d",
    "&hellip;": "\u2026",
    "&bull;": "\u2022",
    "&pound;": "\u00a3",
    "&eacute;": "\u00e9",
}


def resolve_entities(text: str) -> str:
    """
    Resolve HTML entities in API text to unicode characters.
    Does NOT escape for XML — call :func:`escape_xml` separately when needed.
    """
    text = text.replace("&amp;", "&")
    for entity, replacement in HTML_ENTITY_MAP.items():
        text = text.replace(entity, replacement)
    # Replace any remaining HTML entities with a space
    text = re.sub(r"&[a-zA-Z]+;", " ", text)
    return text


def escape_xml(text: str) -> str:
    """Escape bare ``&``, ``<``, ``>`` for safe embedding in XML."""
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    return text


def clean_text(text: str) -> str:
    """
    Clean up text from the API — resolve HTML entities and normalise whitespace.
    Ensures the result is safe for embedding in XML (no HTML passthrough).
    """
    text = text.strip()
    text = resolve_entities(text)
    text = escape_xml(text)
    # Collapse multiple spaces
    text = re.sub(r"  +", " ", text)
    return text


def strip_html_tags(text: str) -> str:
    """Remove all HTML/XML tags from text, leaving just the text content."""
    return re.sub(r"<[^>]+>", " ", text)
