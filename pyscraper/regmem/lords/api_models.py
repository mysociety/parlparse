"""
Models for accessing the Lords Register of Members' Interests API.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import httpx
from pydantic import (
    AliasChoices,
    AliasGenerator,
    BaseModel,
    ConfigDict,
    HttpUrl,
    RootModel,
)
from pydantic.alias_generators import to_camel


def multi_to_camel(value: str) -> AliasChoices:
    converted = to_camel(value)
    return AliasChoices(converted, value)


class SnakeModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=AliasGenerator(validation_alias=multi_to_camel),
        populate_by_name=True,
        extra="ignore",
    )


class Party(SnakeModel):
    id: int
    name: str
    abbreviation: Optional[str] = None
    background_colour: Optional[str] = None
    foreground_colour: Optional[str] = None
    is_lords_main_party: Optional[bool] = None
    is_lords_spiritual_party: Optional[bool] = None
    government_type: Optional[int] = None
    is_independent_party: Optional[bool] = None


class MembershipStatus(SnakeModel):
    status_is_active: Optional[bool] = None
    status_description: Optional[str] = None
    status_notes: Optional[str] = None
    status_id: Optional[int] = None
    status: Optional[int] = None
    status_start_date: Optional[datetime] = None


class LatestHouseMembership(SnakeModel):
    membership_from: Optional[str] = None
    membership_from_id: Optional[int] = None
    house: Optional[int] = None
    membership_start_date: Optional[datetime] = None
    membership_end_date: Optional[datetime] = None
    membership_end_reason: Optional[str] = None
    membership_end_reason_notes: Optional[str] = None
    membership_end_reason_id: Optional[int] = None
    membership_status: Optional[MembershipStatus] = None


class Member(SnakeModel):
    id: int
    name_list_as: Optional[str] = None
    name_display_as: Optional[str] = None
    name_full_title: Optional[str] = None
    name_address_as: Optional[str] = None
    latest_party: Optional[Party] = None
    gender: Optional[str] = None
    latest_house_membership: Optional[LatestHouseMembership] = None
    thumbnail_url: Optional[HttpUrl] = None


class Interest(SnakeModel):
    id: int
    interest: str
    created_when: Optional[datetime] = None
    last_amended_when: Optional[datetime] = None
    deleted_when: Optional[datetime] = None
    is_correction: Optional[bool] = None
    child_interests: list[Interest] = []  # recursive


class InterestCategory(SnakeModel):
    id: int
    name: str
    sort_order: Optional[int] = None
    interests: list[Interest] = []


class Value(SnakeModel):
    member: Member
    interest_categories: list[InterestCategory] = []


class Item(SnakeModel):
    value: Value
    links: Optional[Any] = None


class ItemCollection(RootModel[list[Item]]):
    """Top-level model representing a list of Items."""

    root: list[Item]

    def __iter__(self):
        return iter(self.root)

    def __len__(self):
        return len(self.root)

    def extend(self, items: ItemCollection):
        self.root.extend(items.root)

    @classmethod
    def from_path(cls, path: Path) -> ItemCollection:
        """Load this resource from a file path."""
        with path.open("r", encoding="utf-8") as f:
            return cls.model_validate_json(f.read())

    @classmethod
    def get_from_api(cls) -> ItemCollection:
        """
        Get the current version from the API.
        Pages through results until all items are retrieved.
        """
        url = "https://members-api.parliament.uk/api/LordsInterests/Register"
        all_items = ItemCollection(root=[])
        page = 0

        while True:
            response = httpx.get(url, params={"page": page})
            response.raise_for_status()
            data = response.json()
            items = data.get("items", [])
            if not items:
                break
            page_item = ItemCollection.model_validate(items)
            all_items.extend(page_item)
            page += 1

        return all_items

    def to_path(self, path: Path):
        """Get the path for this resource based on its ID."""
        with path.open("w", encoding="utf-8") as f:
            f.write(self.model_dump_json(indent=2))
