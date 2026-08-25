"""Source data models for Westminster posts and committee memberships."""

from __future__ import annotations

from datetime import date
from typing import NamedTuple

from mysoc_validator.models.popolo import Organization


class Post(NamedTuple):
    """A dated parliamentary post held by one MNIS member."""

    member_id: int
    post_type: str
    post_id: int
    name: str
    start_date: date
    end_date: date | None


class CommitteeRole(NamedTuple):
    """One dated role within a committee membership."""

    name: str | None
    is_chair: bool
    start_date: date
    end_date: date | None


class CommitteeMetadata(NamedTuple):
    """Descriptive and categorical metadata for one committee."""

    id: int
    name: str
    house: str | None = None
    end_date: date | None = None
    parent_id: int | None = None
    categories: tuple[str, ...] = ()
    description: str | None = None
    external_url: str | None = None


class CommitteeMembership(NamedTuple):
    """A member and their dated roles on one committee."""

    member_id: int
    committee_id: int
    committee_name: str
    roles: list[CommitteeRole]
    metadata: CommitteeMetadata | None = None


class MembershipKey(NamedTuple):
    """Stable components used to allocate membership ID suffixes."""

    member_id: int
    membership_type: str
    source_id: int


class CachedCommitteeRecord(NamedTuple):
    """Committee fields recovered from one cached Popolo organization."""

    organization: Organization
    committee_id: int
    external_url: str
