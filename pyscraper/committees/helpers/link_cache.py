"""
Shared cached-link lookup for committee scrapers.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from mysoc_validator import Popolo
from mysoc_validator.models.popolo import Organization


def cached_organization_links(
    output_path: Path,
    *,
    link_prefix: str,
    key: Callable[[Organization], str],
) -> dict[str, str] | None:
    """
    Read a previous Popolo output's organization links matching a URL prefix.

    Returns None when there is no previous output to read. An empty mapping
    is a valid result and distinct from that: it means the previous output
    existed but contained no matching links.
    """
    if not output_path.exists():
        return None
    previous = Popolo.from_path(output_path, cross_validate=False)
    links: dict[str, str] = {}
    for organization in previous.organizations:
        public_link = next(
            (link for link in organization.links if link.startswith(link_prefix)),
            None,
        )
        if public_link:
            links[key(organization)] = public_link
    return links
