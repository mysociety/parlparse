"""
One-off script to add Scottish Parliament IDs
based on the current date.

uv run scripts/add_scottish_ids.py
"""

# /// script
# requires-python = ">=3.9,<3.10"
# dependencies = [
#     "httpx",
#     "mysoc-validator==0.8",
# ]
# ///

import datetime
from pathlib import Path
from typing import Optional

import httpx
import rich
from mysoc_validator import Popolo
from mysoc_validator.models.popolo import Chamber, IdentifierScheme
from mysoc_validator.models.popolo import (
    Person as PopoloPerson,
)
from pydantic import AliasGenerator, BaseModel, ConfigDict, TypeAdapter
from pydantic.alias_generators import to_pascal as base_pascal

dataset_url = "https://data.parliament.scot/api/members"


def to_pascal(name: str) -> str:
    first_round = base_pascal(name)
    return first_round.replace("Id", "ID")


convert_config = ConfigDict(alias_generator=AliasGenerator(validation_alias=to_pascal))


class Person(BaseModel):
    model_config = convert_config
    person_id: int
    photo_url: Optional[str] = None
    notes: str
    birth_date: Optional[datetime.date] = None
    birth_date_is_protected: bool
    parliamentary_name: str
    preferred_name: str
    gender_type_id: int
    is_current: bool


def get_scotapi_data():
    data = httpx.get(dataset_url).json()
    entries = TypeAdapter(list[Person]).validate_python(data)

    pop = Popolo.from_path(Path("members", "people.json"))

    def get_reversed_result(name: str, date: datetime.datetime) -> PopoloPerson:
        manual_fixes = {"Natalie Don-Innes": "Natalie Don", "Ash Regan": "Ash Denham"}

        # take a last name, first name, convert to first name last name and return the person object
        last, first = [x.strip() for x in name.split(",")]
        correct_name = f"{first} {last}".strip()

        if correct_name.startswith("Dr "):
            correct_name = correct_name[3:]

        alt_name = None
        if correct_name in manual_fixes:
            alt_name = manual_fixes[correct_name]

        for name in [correct_name, alt_name]:
            if name:
                result = pop.persons.from_name(
                    name, chamber_id=Chamber.SCOTLAND, date=date.date()
                )
                if result:
                    break
        if result is None:
            raise ValueError(f"Could not find {correct_name} or {alt_name} on {date}")
        return result

    unmatched = []

    current_entries = [e for e in entries if e.is_current]
    date = datetime.datetime.now()

    map = {}

    for e in current_entries:
        try:
            person = get_reversed_result(e.parliamentary_name, date)
            map[person.id] = e.person_id
        except ValueError:
            unmatched.append(e.parliamentary_name)

    unmatched = list(set(unmatched))
    unmatched.sort()

    if unmatched:
        raise ValueError(f"Unmatched names: {unmatched}")

    added_count = 0
    for person_id, scot_id in map.items():
        person = pop.persons[person_id]

        if person.add_identifer(
            scheme=IdentifierScheme.SCOTPARL, identifier=str(scot_id), if_missing=True
        ):
            added_count += 1

    rich.print(f"Added [green]{added_count}[/green] Scottish Parliament IDs")

    pop.to_path(Path("members", "people.json"))


if __name__ == "__main__":
    get_scotapi_data()
