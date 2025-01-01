from __future__ import annotations

import datetime
from hashlib import md5
from pathlib import Path
from typing import Any, Literal, Optional

from mysoc_validator.models.consts import Chamber
from pydantic import BaseModel, Field, computed_field


class GenericRegmemDetail(BaseModel):
    """
    Flexible model for storing key-value information about an interest.

    This is mostly expressing the complexity of the Commons register.

    Details can also have sub-items.

    This is used for
    'declaring interest of trip' (entry)
    'leg of journey' (detail)
    'details about leg' (detail sub-item)

    (In the Commons version of this this is groups of lists of details - but this
    didn't in practice seem to be doing much so it's just one list of details here. )

    """

    name: Optional[str] = None
    description: Optional[str] = None
    type: Optional[str] = None  # string, etc
    value: Optional[Any] = None
    sub_items: list[GenericRegmemDetail] = Field(default_factory=list)


class GenericRegmemEntry(BaseModel):
    """
    The core entry where the actual details are.

    The complexity here mostly reflects the Commons register.

    There are concepts of child interests and details.

    Details are a set of key-value pairs (ish - see GenericRegmemDetail).

    Child interests will represent multiple payments from a single source.

    The description for the Commons will be the 'summary' of the interest.

    The Senedd register also uses Details to store information - but does not have a summary.

    When this is storing XML from the legacy format, the description_format is set to 'xml'.

    """

    description: str = ""
    description_format: Literal["string", "xml"] = "string"
    original_id: Optional[str] = ""
    date_registered: Optional[datetime.date] = None  # or lodged
    date_published: Optional[datetime.date] = None
    date_updated: Optional[datetime.date] = None
    date_received: Optional[datetime.date] = None
    details: list[GenericRegmemDetail] = Field(default_factory=list)
    sub_items: list[GenericRegmemEntry] = Field(default_factory=list)

    @computed_field
    @property
    def comparable_id(self) -> str:
        if self.original_id:
            return self.original_id
        return self.item_hash

    @computed_field
    @property
    def item_hash(self) -> str:
        hash_cols = [
            "description",
            "date_registered",
            "date_published",
            "date_updated",
            "original_id",
            "details",
        ]
        data = self.model_dump(include=set(hash_cols))
        data["sub_items"] = [x.item_hash for x in self.sub_items]
        return md5(str(data).encode()).hexdigest()[:10]


class GenericRegmemCategory(BaseModel):
    """
    Across all registers there are different categories of interests.
    We mostly use these to structure the output - they vary by chamber.

    *Ideally* category_id is a number, or at least sortable.

    """

    category_id: str
    category_name: str
    category_description: Optional[str] = None
    legislation_or_rule_name: Optional[str] = None
    legislation_or_rule_url: Optional[str] = None
    entries: list[GenericRegmemEntry] = Field(default_factory=list)


class GenericRegmemPerson(BaseModel):
    """
    All registered interests for a person.
    Duplicate published_date here with overall register because sometimes
    we know the individual date of publication.
    """

    person_id: str
    person_name: str
    published_date: datetime.date
    categories: list[GenericRegmemCategory] = Field(default_factory=list)


class GenericRegmemRegister(BaseModel):
    """
    General container for a specific release of a register in a chamber.
    This may in practice be "the public information as of date" rather
    than an explicitly released register.
    """

    chamber: Chamber
    language: Literal["en", "cy"] = "en"
    published_date: datetime.date
    entries: list[GenericRegmemPerson] = Field(default_factory=list)

    @classmethod
    def from_path(cls, path: Path):
        data = path.read_text()
        return cls.model_validate_json(data)

    def to_path(self, path: Path):
        data = self.model_dump_json(indent=2, exclude_none=True, exclude_defaults=True)
        path.write_text(data)
