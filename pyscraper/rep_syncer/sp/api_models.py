"""
Pydantic models for the Scottish Parliament API responses and the composite
SPMembership record used as an intermediary between fetch and sync phases.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, ClassVar, Literal, NamedTuple, Optional, TypeVar

import httpx
from mysoc_validator.models.consts import MembershipReason
from pydantic import BaseModel, BeforeValidator, ConfigDict
from pydantic.alias_generators import to_pascal as base_pascal
from pydantic_store import ListModel
from typing_extensions import Self

API_BASE = "https://data.parliament.scot/api"

T = TypeVar("T")


def to_pascal(name: str) -> str:
    return base_pascal(name).replace("Id", "ID")


def parse_api_date(v: object) -> date | None:
    if v is None:
        return None
    if isinstance(v, str):
        return datetime.fromisoformat(v).date()
    if isinstance(v, date):
        return v
    raise ValueError(f"Cannot parse date from {v!r}")


ApiDate = Annotated[date, BeforeValidator(parse_api_date)]
OptApiDate = Annotated[Optional[date], BeforeValidator(parse_api_date)]


class FetchableListModel(ListModel[T]):
    url: ClassVar[str]

    @classmethod
    def fetch(cls) -> Self:
        response = httpx.get(cls.url, timeout=30)
        response.raise_for_status()
        return cls.model_validate(response.json())


class SpApiModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_pascal, populate_by_name=True)


class PersonName(NamedTuple):
    first_name: str
    last_name: str


class Member(SpApiModel):
    person_id: int
    parliamentary_name: str
    preferred_name: str
    is_current: bool


class MemberList(FetchableListModel[Member]):
    url: ClassVar[str] = f"{API_BASE}/members/json"

    def name_lookup(self) -> dict[int, PersonName]:
        return {
            m.person_id: PersonName(
                first_name=m.preferred_name.strip(),
                last_name=m.parliamentary_name.split(",")[0].strip(),
            )
            for m in self
        }


class MemberParty(SpApiModel):
    """Party assignment for a member (= membership period in Popolo terms)."""

    id: int
    person_id: int
    party_id: int
    valid_from_date: ApiDate
    valid_until_date: OptApiDate


class MemberPartyList(FetchableListModel[MemberParty]):
    url: ClassVar[str] = f"{API_BASE}/memberparties/json"


class Party(SpApiModel):
    id: int
    abbreviation: str
    actual_name: str
    preferred_name: str


class PartyList(FetchableListModel[Party]):
    url: ClassVar[str] = f"{API_BASE}/parties/json"

    def name_lookup(self) -> dict[int, str]:
        return {p.id: p.actual_name for p in self}


class MemberElectionConstituencyStatus(SpApiModel):
    id: int
    person_id: int
    constituency_id: int
    valid_from_date: ApiDate
    valid_until_date: OptApiDate


class MemberElectionConstituencyStatusList(
    FetchableListModel[MemberElectionConstituencyStatus]
):
    url: ClassVar[str] = f"{API_BASE}/MemberElectionConstituencyStatuses/json"


class MemberElectionRegionStatus(SpApiModel):
    id: int
    person_id: int
    region_id: int
    valid_from_date: ApiDate
    valid_until_date: OptApiDate


class MemberElectionRegionStatusList(FetchableListModel[MemberElectionRegionStatus]):
    url: ClassVar[str] = f"{API_BASE}/MemberElectionregionStatuses/json"


class Region(SpApiModel):
    id: int
    region_code: str
    name: str
    start_date: ApiDate
    end_date: OptApiDate


class RegionList(FetchableListModel[Region]):
    url: ClassVar[str] = f"{API_BASE}/regions/json"

    def by_id(self) -> dict[int, Region]:
        return {r.id: r for r in self}


class Constituency(SpApiModel):
    id: int
    constituency_code: str
    name: str
    valid_from_date: ApiDate
    valid_until_date: OptApiDate


class ConstituencyList(FetchableListModel[Constituency]):
    url: ClassVar[str] = f"{API_BASE}/constituencies/json"

    def by_id(self) -> dict[int, Constituency]:
        return {c.id: c for c in self}


class SPMembership(BaseModel):
    """
    Flat composite record joining party, person, and location data.
    """

    membership_id: int
    scottish_parl_person_id: int
    first_name: str
    last_name: str
    party: str
    start_date: date
    end_date: Optional[date]
    constituency_or_region: Literal["constituency", "region"]
    constituency_or_region_name: str
    cycle_start: date
    cycle_end: Optional[date]  # None if the election cycle is still open
    start_reason: MembershipReason = MembershipReason.BLANK
    end_reason: MembershipReason = MembershipReason.BLANK


class SPMembershipList(ListModel[SPMembership]):
    pass
