"""Small iterable helpers shared by committee scrapers."""

from collections.abc import Hashable, Iterable
from typing import TypeVar

Item = TypeVar("Item", bound=Hashable)


def unique(items: Iterable[Item]) -> list[Item]:
    """Return first occurrences in input order."""
    return list(dict.fromkeys(items))
