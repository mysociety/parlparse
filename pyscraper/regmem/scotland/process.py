import datetime
from functools import lru_cache
from itertools import groupby
from typing import Optional

import requests
from mysoc_validator.models.consts import Chamber, IdentifierScheme
from mysoc_validator.models.interests import (
    RegmemCategory,
    RegmemEntry,
    RegmemPerson,
    RegmemRegister,
)
from pydantic import TypeAdapter
from tqdm import tqdm

from pyscraper.regmem.funcs import get_popolo, parldata_path
from pyscraper.regmem.legacy_converter import write_register_to_xml
from pyscraper.regmem.scotland.api_models import ScotAPIEntry

dataset_url = "https://data.parliament.scot/api/registerofinterest"

missing_id_warning = []


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


def process_category(entries: list[ScotAPIEntry]) -> RegmemCategory:
    """
    Convert a set of entries related to a category into a category entry.
    """
    initial_entry = entries[0]
    category_name = initial_entry.detail.name

    category = RegmemCategory(category_id=category_name, category_name=category_name)

    for entry in entries:
        universal_entry = RegmemEntry(
            content=entry.detail.description,
            null_entry=entry.detail.description == "No registrable interests",
            id=entry.id,
            date_registered=entry.detail.date_lodged.date(),
            date_updated=entry.updated_date.date() if entry.updated_date else None,
            date_published=entry.updated_date.date() if entry.updated_date else None,
        )

        category.entries.append(universal_entry)

    return category


def process_person(
    entries: list[ScotAPIEntry], date_for_lookup: datetime.date, quiet: bool = False
) -> Optional[RegmemPerson]:
    """
    Convert a list of entries related to a person into a person entry.
    """
    initial_entry = entries[0]
    scot_id = initial_entry.person.id

    try:
        pop_person = get_popolo().persons.from_identifier(
            str(scot_id), scheme=IdentifierScheme.SCOTPARL
        )
    except ValueError:
        # if we don't have the ID, we don't process them
        # so we're not getting all the historical data, but
        # it's not worth getting the name matching working well.
        if not quiet:
            if scot_id not in missing_id_warning:
                # only print once
                missing_id_warning.append(scot_id)
                tqdm.write(f"Can't find person from identifer: {scot_id}")
        return None

    our_id = pop_person.id
    our_name = pop_person.get_main_name(date_for_lookup)
    if not our_name:
        raise ValueError(
            f"Could not find name for person {our_id} on {date_for_lookup}"
        )
    our_name = our_name.nice_name()

    person_entry = RegmemPerson(
        person_id=our_id,
        person_name=our_name,
        published_date=date_for_lookup,
        chamber=Chamber.SCOTLAND,
    )

    # name is the category name
    entries = sorted(entries, key=lambda x: x.detail.name)

    for category_name, group in groupby(entries, key=lambda x: x.detail.name):
        group = list(group)
        person_entry.categories.append(process_category(group))

    return person_entry


def create_register_file_for_date(
    register_date: datetime.date, force_refresh: bool = False, quiet: bool = False
):
    """
    Actually create the relevant register json and xml for a date.
    """
    dest_folder = parldata_path / "scrapedjson" / "universal_format_regmem" / Chamber.SCOTLAND

    if not dest_folder.exists():
        dest_folder.mkdir(exist_ok=True, parents=True)

    dest_path = dest_folder / f"scotland-regmem{register_date}.json"

    if not dest_path.exists() or force_refresh:
        register = process_all_people(register_date, quiet=quiet)
        register.to_path(dest_path)
        write_register_to_xml(
            register, xml_folder_name="regmem-scotparl", force_refresh=force_refresh
        )


def process_all_people(
    register_date: datetime.date, quiet: bool = False
) -> RegmemRegister:
    """
    Convert the all time json to a specific folder.
    """
    entries = get_data()

    # invalidate data by time
    # we to invalidate things that are updated *after* register_date,
    # or invalidate those that have an end date *before* register_date.

    # also, we want to remove any date_reviewed more than a year before review_cut_off.

    # set a cut off date of a year before
    review_cut_off = register_date - datetime.timedelta(days=365)

    entries = [
        x for x in entries if x.time.end is None or x.time.end.date() >= register_date
    ]
    entries = [
        x for x in entries if x.updated_date and x.updated_date.date() <= register_date
    ]

    entries = [x for x in entries if x.detail.date_reviewed.date() >= review_cut_off]

    # ok, so there's a problem where for the historical record, updates are kind of invisible, not linked, and old entries
    # not depricated. So we need to remove duplicate person_ids,description, and date_lodged

    entries = sorted(entries, key=lambda x: x.detail.interest_id, reverse=True)

    deduped_entries = []
    deduped_keys = []

    for entry in entries:
        key = (
            entry.person.id,
            entry.detail.description,
            entry.detail.date_lodged,
            entry.detail.name,
        )
        if key not in deduped_keys:
            deduped_keys.append(key)
            deduped_entries.append(entry)

    register = RegmemRegister(
        chamber=Chamber.SCOTLAND,
        published_date=register_date,
    )

    entries = deduped_entries
    entries.sort(key=lambda x: x.person.id)

    for person_id, group in groupby(entries, key=lambda x: x.person.id):
        group = list(group)
        person = process_person(group, register_date, quiet=quiet)
        if person:
            register.persons.append(person)

    return register


def download_all_registers(
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
        create_register_file_for_date(date, force_refresh=force_refresh, quiet=quiet)


if __name__ == "__main__":
    download_all_registers(force_refresh=True)
