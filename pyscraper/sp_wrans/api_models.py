import datetime
from typing import Optional

from pydantic import AliasGenerator, BaseModel, ConfigDict
from pydantic.alias_generators import to_pascal as base_pascal


def to_pascal(name: str) -> str:
    first_round = base_pascal(name)
    return first_round.replace("Id", "ID").replace("Msp", "MSP")


convert_config = ConfigDict(
    alias_generator=AliasGenerator(validation_alias=to_pascal), extra="forbid"
)


class SPQuestion(BaseModel):
    """
    Model for a question from the Scottish Parliament
    motionsquestionsanswersquestions API.
    """

    model_config = convert_config

    unique_id: int
    event_id: str
    event_type_id: int
    event_sub_type_id: int
    msp_id: int
    party: str
    region_id: Optional[int] = None
    constituency_id: Optional[int] = None
    approved_date: Optional[datetime.datetime] = None
    submission_date_time: Optional[datetime.datetime] = None
    title: str
    item_text: str
    answer_text: Optional[str] = None
    answer_date: Optional[datetime.datetime] = None
    answer_status_id: Optional[int] = None
    expected_answer_date: Optional[datetime.datetime] = None
    meeting_date: Optional[datetime.datetime] = None
    answered_by_msp: Optional[str] = None
    on_behalf_of: Optional[str] = None
    considered_for_members_business: Optional[bool] = False
    cross_party_support: Optional[bool] = False
    registered_interest: Optional[bool] = False

    @property
    def is_written(self) -> bool:
        """Written questions have EventIDs starting with S<n>W."""
        return len(self.event_id) > 2 and self.event_id[2] == "W"

    @property
    def is_answered(self) -> bool:
        return self.answer_date is not None and bool(self.answer_text)

    @property
    def answer_date_only(self) -> Optional[datetime.date]:
        if self.answer_date:
            return self.answer_date.date()
        return None

    @property
    def submission_date_only(self) -> Optional[datetime.date]:
        if self.submission_date_time:
            return self.submission_date_time.date()
        elif self.approved_date:
            return self.approved_date.date()
        return None
