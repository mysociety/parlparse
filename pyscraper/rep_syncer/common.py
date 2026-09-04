"""
Generic helpers for working with Popolo data and membership date ranges.
"""

from __future__ import annotations

from datetime import date
from typing import Optional, Protocol

from mysoc_validator import Popolo
from mysoc_validator.models.dates import FixedDate
from mysoc_validator.models.popolo import Membership, Post


class HasDateRange(Protocol):
    start_date: date
    end_date: date | None


def dates_close(a: date, b: date, tolerance_days: int) -> bool:
    return abs((a - b).days) <= tolerance_days


def is_open_ended(m: Membership) -> bool:
    """
    True if the membership has no real end date
    """
    return m.end_date == FixedDate.FUTURE


def memberships_for_person_and_post(
    popolo: Popolo, person_id: str, post_id: str
) -> list[Membership]:
    """
    Return all memberships in people.json for a given person + post combination.
    """
    return [
        m
        for m in popolo.memberships
        if isinstance(m, Membership)
        and m.person_id == person_id
        and m.post_id == post_id
    ]


def membership_overlaps(source: HasDateRange, existing: Membership) -> bool:
    """
    True if a source membership date range overlaps with a Popolo Membership.
    A None source end_date is treated as open-ended.
    """
    source_end = source.end_date or FixedDate.FUTURE
    return source.start_date <= existing.end_date and source_end >= existing.start_date


def find_post(
    popolo: Popolo, area_name: str, org_id: str, on_date: date | None = None
) -> Optional[Post]:
    """
    Return the post for the given organisation whose area name matches, or None.
    If on_date is given, posts that ended before that date are skipped, so that
    reused area names resolve to the currently-active post rather than a historical one.
    """
    for post in popolo.posts:
        if post.organization_id != org_id or post.area.name != area_name:
            continue
        if on_date is not None and post.end_date is not None:
            if post.end_date < on_date:
                continue
        return post
    return None
