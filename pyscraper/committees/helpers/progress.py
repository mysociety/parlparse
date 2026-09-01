"""Consistent terminal progress for committee scrapers."""

from __future__ import annotations

from collections.abc import Generator, Iterable
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator, TypeVar

from tqdm import tqdm

Item = TypeVar("Item")
_VERBOSE = ContextVar("committees_verbose", default=True)


def is_verbose() -> bool:
    """Return whether the current scraper context should emit progress output."""
    return _VERBOSE.get()


@contextmanager
def set_verbose(verbose: bool) -> Generator[None]:
    """Temporarily configure progress output for the current execution context."""
    token = _VERBOSE.set(verbose)
    try:
        yield
    finally:
        _VERBOSE.reset(token)


def track(
    items: Iterable[Item],
    description: str,
    *,
    total: int | None = None,
) -> Iterator[Item]:
    """Iterate with a transient progress bar when verbose output is enabled."""
    return iter(
        tqdm(
            items,
            desc=description,
            total=total,
            leave=False,
            disable=not is_verbose(),
        )
    )


def report(message: str) -> None:
    """Write a message without disrupting an active progress bar."""
    if is_verbose():
        tqdm.write(message)
