import datetime
from pathlib import Path

from pydantic import AliasGenerator, BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_pascal

convert_config = ConfigDict(
    alias_generator=AliasGenerator(validation_alias=to_pascal), extra="forbid"
)


class NIAPIPersonInterest(BaseModel):
    model_config = convert_config
    person_id: int
    member_name: str
    register_category_id: int
    register_category: str
    register_entry: str
    register_entry_start_date: datetime.datetime


class NIAPIRegisteredInterests(BaseModel):
    model_config = convert_config
    registered_interest: list[NIAPIPersonInterest] = Field(default_factory=list)


class NIAPIRegister(BaseModel):
    model_config = convert_config
    all_registered_interests: NIAPIRegisteredInterests

    @classmethod
    def from_path(cls, path: Path):
        data = path.read_text()
        return cls.model_validate_json(data)

    def __iter__(self):
        return iter(self.all_registered_interests.registered_interest)
