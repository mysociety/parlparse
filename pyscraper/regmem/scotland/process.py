import datetime
from functools import lru_cache
from itertools import groupby
from typing import Optional

import requests
from mysoc_validator import Popolo
from mysoc_validator.models.consts import Chamber, IdentifierScheme
from pydantic import TypeAdapter
from tqdm import tqdm

from pyscraper.regmem.funcs import memberdata_path, parldata_path
from pyscraper.regmem.legacy_converter import write_register_to_xml
from pyscraper.regmem.models import (
    GenericRegmemCategory,
    GenericRegmemEntry,
    GenericRegmemPerson,
    GenericRegmemRegister,
)
from pyscraper.regmem.scotland.api_models import ScotAPIEntry

dataset_url = "https://data.parliament.scot/api/registerofinterest"


@lru_cache
def get_popolo() -> Popolo:
    return Popolo.from_path(memberdata_path / "people.json")


@lru_cache
def get_data(dump_rejected: bool = True):
    """
    Basic fetch of the data from the API.
    Excluding 'rejected' items - which seems right, but might need to be revisited.
    (There's not many.)
    """
    data = requests.get(dataset_url).json()
    entries = TypeAdapter(list[ScotAPIEntry]).validate_python(data)
    if dump_rejected:
        entries = [
            entry for entry in entries if entry.detail.approval_status != "Rejected"
        ]
    return entries


def fix_parliamentary_name(name: str) -> str:
    """
    Fix last name, first name to first name last name
    """
    parts = [x.strip() for x in name.split(", ")]
    if len(parts) == 2:
        return f"{parts[1]} {parts[0]}"
    return name


def process_category(entries: list[ScotAPIEntry]) -> GenericRegmemCategory:
    """
    Convert a set of entries related to a category into a category entry.
    """
    initial_entry = entries[0]
    category_name = initial_entry.detail.name

    category = GenericRegmemCategory(
        category_id=category_name, category_name=category_name
    )

    for entry in entries:
        generic_entry = GenericRegmemEntry(
            description=entry.detail.description,
            original_id=entry.id,
            date_registered=entry.detail.date_lodged.date(),
            date_updated=entry.updated_date.date() if entry.updated_date else None,
            date_published=entry.updated_date.date() if entry.updated_date else None,
        )

        category.entries.append(generic_entry)

    return category


def process_person(
    entries: list[ScotAPIEntry], date_for_lookup: datetime.date
) -> Optional[GenericRegmemPerson]:
    """
    Convert a list of entries related to a person into a person entry.
    """
    initial_entry = entries[0]
    scot_id = initial_entry.person.id
    our_name = fix_parliamentary_name(initial_entry.person.parliamentary_name)

    try:
        pop_person = get_popolo().persons.from_identifier(
            str(scot_id), scheme=IdentifierScheme.SCOTPARL
        )
    except ValueError:
        # if we don't have the ID, we don't process them
        # so we're not getting all the historical data, but
        # it's not worth getting the name matching working well.
        return None

    our_id = pop_person.id

    person_entry = GenericRegmemPerson(
        person_id=our_id, person_name=our_name, published_date=date_for_lookup
    )

    # name is the category name
    entries = sorted(entries, key=lambda x: x.detail.name)

    for category_name, group in groupby(entries, key=lambda x: x.detail.name):
        group = list(group)
        person_entry.categories.append(process_category(group))

    return person_entry


def create_register_file_for_date(
    register_date: datetime.date, force_refresh: bool = False
):
    """
    Actually create the relevant register json and xml for a date.
    """
    dest_folder = parldata_path / "scrapedjson" / "common_regmem" / Chamber.SCOTLAND

    if not dest_folder.exists():
        dest_folder.mkdir(exist_ok=True, parents=True)

    dest_path = dest_folder / f"scotland-regmem{register_date}.json"

    if not dest_path.exists() or force_refresh:
        register = process_all_people(register_date)
        register.to_path(dest_path)
        write_register_to_xml(
            register, xml_folder_name="regmem-scotparl", force_refresh=force_refresh
        )


def process_all_people(register_date: datetime.date) -> GenericRegmemRegister:
    """
    Convert the all time json to a specific folder.
    """
    entries = get_data()

    # invalidate data by time
    # we want things that are updated *after* this date,
    # or that have an end date *before* this date.
    entries = [
        x for x in entries if x.time.end is None or x.time.end.date() >= register_date
    ]
    entries = [
        x for x in entries if x.updated_date and x.updated_date.date() <= register_date
    ]

    entries.sort(key=lambda x: x.person.id)

    register = GenericRegmemRegister(
        chamber=Chamber.SCOTLAND,
        published_date=register_date,
    )

    for person_id, group in groupby(entries, key=lambda x: x.person.id):
        group = list(group)
        person = process_person(group, register_date)
        if person:
            register.entries.append(person)

    return register


def get_updated_dates(
    latest_only: bool = False,
    force_refresh: bool = False,
    quiet: bool = False,
    no_progress: bool = False,
):
    """
    Get a set of dates when the register has been updated.
    These are our pseudo "published" dates.
    """
    entries = get_data()

    updated_dates = [x.updated_date.date() for x in entries if x.updated_date]
    updated_dates = list(set(updated_dates))
    updated_dates.sort()

    if latest_only:
        updated_dates = [updated_dates[-1]]

    for date in tqdm(updated_dates, disable=quiet or no_progress):
        create_register_file_for_date(date, force_refresh=force_refresh)


if __name__ == "__main__":
    get_updated_dates(force_refresh=True)