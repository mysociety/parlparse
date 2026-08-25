"""Source data models for Northern Ireland Assembly committees."""

from __future__ import annotations

from typing import NamedTuple


class Committee(NamedTuple):
    id: int
    name: str
    committee_type: str
    external_url: str | None = None


class AssemblyPerson(NamedTuple):
    person_id: int
    name: str


class MemberRole(NamedTuple):
    affiliation_id: int
    person_id: int
    role_type: str
    role: str
    committee_id: int
    organization_name: str = ""
    affiliation_title: str | None = None
    start_date: str | None = None
    end_date: str | None = None


class NorthernIrelandAssemblyData(NamedTuple):
    """Committee and role datasets returned by the Assembly API."""

    committees: list[Committee]
    roles: list[MemberRole]


class CommitteeMembershipKey(NamedTuple):
    """Fields that uniquely identify a person on an Assembly committee."""

    committee_id: int
    person_id: int
