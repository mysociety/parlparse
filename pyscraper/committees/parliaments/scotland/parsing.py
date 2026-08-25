"""Parse Scottish Parliament public committee pages."""

from __future__ import annotations

from urllib.parse import urljoin

from bs4 import BeautifulSoup

COMMITTEE_INDEX_URL = (
    "https://www.parliament.scot/chamber-and-committees/committees/"
    "current-and-previous-committees"
)


def parse_committee_links(html: str) -> dict[str, str]:
    """Map committee names to their public pages from the official index."""
    soup = BeautifulSoup(html, "html.parser")
    links: dict[str, str] = {}
    path_fragment = "/committees/current-and-previous-committees/"
    for anchor in soup.select("a[href]"):
        href = anchor.get("href")
        if not isinstance(href, str) or path_fragment not in href:
            continue
        name = " ".join(anchor.stripped_strings)
        if name and name.casefold() != "list of committees":
            links.setdefault(name, urljoin(COMMITTEE_INDEX_URL, href))
    return links


def clean_description(value: str) -> str:
    """Normalize API line endings while preserving paragraph breaks."""
    lines = value.replace("\r\n", "\n").replace("\r", "\n").splitlines()
    return "\n".join(line.rstrip() for line in lines).strip()
