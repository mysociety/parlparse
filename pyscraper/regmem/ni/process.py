import datetime
import json
from itertools import groupby

import requests
from mysoc_validator.models.consts import Chamber
from mysoc_validator.models.interests import (
    RegmemCategory,
    RegmemEntry,
    RegmemPerson,
    RegmemRegister,
)
from tqdm import tqdm

from pyscraper.regmem.funcs import get_popolo, parldata_path
from pyscraper.regmem.legacy_converter import write_register_to_xml
from pyscraper.regmem.ni.api_models import NIAPIPersonInterest, NIAPIRegister

dataset_url = (
    "https://data.niassembly.gov.uk/register.asmx/GetAllRegisteredInterests_JSON"
)
dataset_path = parldata_path / "scrapedjson" / "niassembly" / "registerofinterest.json"


def fetch_data_remote():
    """
    Download the data from the API and save it to a file.
    """
    dataset_path.parent.mkdir(parents=True, exist_ok=True)

    data = requests.post(dataset_url).json()
    dataset_path.write_text(json.dumps(data, indent=2))


def get_data() -> list[NIAPIPersonInterest]:
    fetch_data_remote()
    return list(NIAPIRegister.from_path(dataset_path))


def create_ni_universal_for_date(
    entries: list[NIAPIPersonInterest], closing_date: datetime.date
) -> RegmemRegister:
    """
    Convert the all time data into a register for a specific date.
    """
    ni = RegmemRegister(chamber=Chamber.NORTHERN_IRELAND, published_date=closing_date)

    entries.sort(key=lambda x: x.person_id)
    for person_id, person_entries in groupby(entries, key=lambda x: x.person_id):
        person = get_popolo().persons.from_identifier(
            str(person_id), scheme="data.niassembly.gov.uk"
        )
        if person is None:
            print(f"Could not find person with ID {person_id}")
            continue

        person_entries = list(person_entries)
        first_entry = person_entries[0]
        person_name = first_entry.member_name

        person = RegmemPerson(
            person_id=person.id,
            person_name=person_name,
            published_date=closing_date,
            chamber=Chamber.NORTHERN_IRELAND,
        )

        person_entries.sort(key=lambda x: x.register_category_id)
        for category_id, category_entries in groupby(
            person_entries, key=lambda x: x.register_category_id
        ):
            category_entries = list(category_entries)
            first_entry = category_entries[0]
            category_name = first_entry.register_category
            category = RegmemCategory(
                category_id=str(category_id), category_name=category_name
            )
            for entry in category_entries:
                entry = RegmemEntry(
                    content=entry.register_entry,
                    date_published=entry.register_entry_start_date.date(),
                )
                category.entries.append(entry)
            person.categories.append(category)
        ni.persons.append(person)
    return ni


def create_register_file_for_date(
    entries: list[NIAPIPersonInterest],
    register_date: datetime.date,
    force_refresh: bool = False,
):
    dest_folder = (
        parldata_path
        / "scrapedjson"
        / "universal_format_regmem"
        / Chamber.NORTHERN_IRELAND
    )

    if not dest_folder.exists():
        dest_folder.mkdir(exist_ok=True, parents=True)

    dest_path = dest_folder / f"ni-regmem{register_date}.json"

    if not dest_path.exists() or force_refresh:
        register = create_ni_universal_for_date(entries, register_date)
        register.to_path(dest_path)
        write_register_to_xml(
            register, xml_folder_name="regmem-ni", force_refresh=force_refresh
        )


def download_all_registers(
    latest_only: bool = False,
    force_refresh: bool = False,
    quiet: bool = False,
    no_progress: bool = False,
):
    """
    Get possible register dates from the register_entry_start_date
    """
    data = get_data()

    all_dates = [x.register_entry_start_date.date() for x in data]
    # remove duplicates
    all_dates = list(set(all_dates))
    all_dates.sort()

    if latest_only:
        all_dates = [all_dates[-1]]

    for date in tqdm(all_dates, disable=quiet or no_progress):
        reduced_data = [x for x in data if x.register_entry_start_date.date() <= date]
        create_register_file_for_date(reduced_data, date, force_refresh=force_refresh)


if __name__ == "__main__":
    download_all_registers()
