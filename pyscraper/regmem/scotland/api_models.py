import datetime
from typing import Optional

from pydantic import AliasGenerator, BaseModel, ConfigDict, field_validator
from pydantic.alias_generators import to_pascal as base_pascal


def to_pascal(name: str) -> str:
    first_round = base_pascal(name)
    return first_round.replace("Id", "ID")


convert_config = ConfigDict(
    alias_generator=AliasGenerator(validation_alias=to_pascal), extra="forbid"
)


class ScotAPIPerson(BaseModel):
    model_config = convert_config
    id: int
    parliamentary_name: str
    party_name: str
    constituency_name: Optional[str] = None
    constituency_region: Optional[str] = None
    gender: Optional[str] = None
    party_abbreviation: str


class ScotAPIDetail(BaseModel):
    model_config = convert_config
    description: str
    interest_id: int
    name: str
    date_lodged: datetime.datetime
    date_sent: datetime.datetime
    date_reviewed: datetime.datetime
    statement_id: int
    created_by_user_type: str
    approval_status: str
    approval_date_changed: datetime.datetime
    approval_member_message: Optional[str] = None
    date_published_by: datetime.datetime

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        return v.strip()


class ScotAPITime(BaseModel):
    model_config = convert_config
    start: datetime.datetime
    end: Optional[datetime.datetime] = None
    session: str


class ScotAPIEntry(BaseModel):
    model_config = convert_config
    id: str
    person: ScotAPIPerson
    detail: ScotAPIDetail
    time: ScotAPITime
    updated_date: Optional[datetime.datetime] = None
    updated_elastic_date: Optional[datetime.datetime] = None
