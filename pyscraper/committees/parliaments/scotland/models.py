"""
Models for Scottish Parliament committee open data.
"""

from __future__ import annotations

from datetime import date, datetime, time
from typing import NamedTuple

from pydantic import AliasGenerator, BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_pascal as pydantic_to_pascal


def to_api_field_name(name: str) -> str:
    """
    Convert a Python field name to the Scottish Parliament API convention.
    """
    return pydantic_to_pascal(name).replace("Id", "ID")


api_model_config = ConfigDict(
    alias_generator=AliasGenerator(validation_alias=to_api_field_name),
    populate_by_name=True,
)


class DatedRecord(BaseModel):
    """
    Represent an API record with a half-open period of validity.
    """

    model_config = api_model_config

    valid_from: datetime = Field(validation_alias="ValidFromDate")
    valid_until: datetime | None = Field(
        default=None,
        validation_alias="ValidUntilDate",
    )

    def active_on(self, on_date: date) -> bool:
        """
        Return whether the record is active on the supplied date.
        """
        on_datetime = datetime.combine(on_date, time.min)
        return self.valid_from <= on_datetime and (
            self.valid_until is None or on_datetime < self.valid_until
        )


class Committee(DatedRecord):
    """
    Represent a Scottish Parliament committee.
    """

    id: int
    short_name: str = ""
    name: str
    description: str = ""
    committee_email_address: str = ""
    committee_telephone: str = ""
    blog_website: str | None = None


class CommitteeRole(BaseModel):
    """
    Represent a role that a person can hold on a committee.
    """

    model_config = api_model_config

    id: int
    name: str


class PersonCommitteeRole(DatedRecord):
    """
    Represent a person's dated role on a committee.
    """

    id: int
    person_id: int
    committee_role_id: int
    committee_id: int


class ScottishPerson(BaseModel):
    """Represent a person named by the Scottish Parliament API."""

    model_config = api_model_config

    person_id: int
    parliamentary_name: str


class GovernmentRole(BaseModel):
    """Represent a role in the Scottish Government."""

    model_config = api_model_config

    id: int
    name: str


class MemberGovernmentRole(DatedRecord):
    """Represent a person's dated role in the Scottish Government."""

    id: int
    person_id: int
    government_role_id: int


class CommitteeMembershipKey(NamedTuple):
    """Fields that uniquely identify a person on a Scottish committee."""

    committee_id: int
    person_id: int


class CommitteeData(BaseModel):
    """
    Collect the related datasets needed to build committee and government Popolo.
    """

    committees: list[Committee]
    roles: list[CommitteeRole]
    person_roles: list[PersonCommitteeRole]
    government_roles: list[GovernmentRole] = Field(default_factory=list)
    member_government_roles: list[MemberGovernmentRole] = Field(default_factory=list)
    members: list[ScottishPerson] = Field(default_factory=list)
    committee_links: dict[str, str] = Field(default_factory=dict)
