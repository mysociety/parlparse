"""
Reduce committee purpose HTML to plain sentence text.
"""

from __future__ import annotations

from bs4 import BeautifulSoup


def reduce_purpose_html(html: str) -> str:
    """
    Extract and clean sentences from a committee's purpose HTML.

    Paragraphs consisting only of links, and the boilerplate "follow the
    committee on" sentence, are dropped. Remaining sentences are stripped,
    given a trailing full stop, and joined one per line.
    """
    soup = BeautifulSoup(html, "html.parser")
    sentences = []

    for p in soup.find_all("p"):
        text = p.get_text(strip=True)
        for sentence in text.split(". "):
            sentence = sentence.strip()
            if not sentence:
                continue
            if sentence.lower().startswith("you can follow the committee on"):
                continue
            if len(p.find_all("a")) == len(p.contents):  # Only contains links
                continue
            if not sentence.endswith("."):
                sentence += "."
            sentences.append(sentence)

    return "\n".join(sentences)
