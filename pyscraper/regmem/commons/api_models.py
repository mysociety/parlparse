from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Any, List, Optional

from pydantic import AliasChoices, AliasGenerator, BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


def multi_to_camel(value: str) -> AliasChoices:
    converted = to_camel(value)
    return AliasChoices(converted, value)


convert_config = ConfigDict(
    alias_generator=AliasGenerator(validation_alias=multi_to_camel)
)


class CommonsAPIFieldModel(BaseModel):
    model_config = convert_config

    name: Optional[str] = None
    description: Optional[str] = None
    type: Optional[str] = None
    value: Optional[Any] = None
    values: Optional[List[List[CommonsAPIFieldModel]]] = None


class CommonsAPILink(BaseModel):
    model_config = convert_config

    rel: Optional[str] = Field(
        None, description="Relationship of the link to the object requested."
    )
    href: Optional[str] = Field(
        None, description="A complete URL that shows how the action can be performed."
    )
    method: Optional[str] = Field(None, description="Request method of the link.")


class CommonsAPIMember(BaseModel):
    model_config = convert_config

    id: int = Field(description="ID of the member.")
    name_display_as: Optional[str] = Field(
        None,
        description="Member's current full name, as it should be displayed in text.",
    )
    name_list_as: Optional[str] = Field(
        None,
        description="Member's current name in the format {surname}, {forename}, for use in an ordered list.",
    )
    house: Optional[str] = Field(
        None,
        description="The name of the House the Member is currently associated with.",
    )
    member_from: Optional[str] = Field(
        None, description="Constituency of Commons Members."
    )
    party: Optional[str] = Field(
        None, description="Party the Member is currently associated with."
    )
    links: Optional[List[CommonsAPILink]] = Field(
        None,
        description="A list of HATEOAS Links for retrieving further information about this member.",
    )
    categories: List[CommonsAPIPublishedCategory] = Field(default_factory=list)


class RegisterDocument(Enum):
    Full = "Full"
    Updated = "Updated"


class RegisterType(Enum):
    Commons = "Commons"


class CommonsAPIPublishedCategory(BaseModel):
    model_config = convert_config

    id: int = Field(description="ID of the category.")
    number: str = Field(description="Number of the category in the code of conduct.")
    name: Optional[str] = Field(None, description="Name of the category.")
    type: Optional[RegisterType] = None
    links: Optional[List[CommonsAPILink]] = Field(
        None,
        description="A list of HATEOAS Links for retrieving further information about this category.",
    )
    interests: List[CommonsAPIPublishedInterest] = Field(default_factory=list)


class CommonsAPIPublishedInterest(BaseModel):
    model_config = convert_config

    id: int = Field(description="ID of the interest.")
    summary: str = Field(description="Title Summary for the interest.")
    parent_interest_id: Optional[int] = Field(
        None,
        description="The unique ID for the payer (parent interest) to which this payment (child interest) is associated.",
    )
    registration_date: Optional[date] = Field(
        None, description="Registration Date on the published interest."
    )
    published_date: Optional[date] = Field(
        None, description="Date when the interest was first published."
    )
    updated_date: List[date] = Field(
        default_factory=list,
        description="A list of dates on which the interest has been updated since it has been published.",
    )
    category: CommonsAPIPublishedCategory
    member: CommonsAPIMember
    fields: List[CommonsAPIFieldModel] = Field(
        default_factory=list,
        description="List of fields which are available for a member to add further information about the interest.",
    )
    links: Optional[List[CommonsAPILink]] = Field(
        None,
        description="A list of HATEOAS Links for retrieving related information about this interest.",
    )
    child_items: list[CommonsAPIPublishedInterest] = Field(default_factory=list)

    @property
    def last_updated_date(self) -> Optional[date]:
        if self.updated_date:
            return self.updated_date[-1]
        return None


class CommonsAPIPublishedRegister(BaseModel):
    model_config = convert_config

    id: int = Field(description="ID of the register.")
    published_date: date = Field(description="Date when the Register was published.")
    type: Optional[RegisterType] = None
    links: Optional[List[CommonsAPILink]] = Field(
        None,
        description="A list of HATEOAS Links for retrieving related information about this register.",
    )
