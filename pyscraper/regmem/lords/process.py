import datetime
from dataclasses import dataclass
from functools import lru_cache as lrucache
from pathlib import Path
from typing import NamedTuple

import rich
from mysoc_validator import Popolo
from mysoc_validator.models.consts import Chamber
from mysoc_validator.models.interests import (
    RegmemAnnotation,
    RegmemCategory,
    RegmemEntry,
    RegmemPerson,
    RegmemRegister,
)
from mysoc_validator.models.popolo import IdentifierScheme

from pyscraper.regmem.funcs import memberdata_path, parldata_path
from pyscraper.regmem.legacy_converter import write_register_to_xml
from pyscraper.regmem.lords.api_models import Interest, ItemCollection, Member

json_folder = parldata_path / "scrapedjson" / "universal_format_regmem" / Chamber.LORDS


class PersonInfo(NamedTuple):
    """Result from matching a Lords member to a person in the popolo data."""

    person_id: str
    person_name: str


class RegisterData(NamedTuple):
    """Result from downloading and storing raw register data."""

    data: ItemCollection
    register_date: datetime.date


def slugify(s: str) -> str:
    """
    Convert a string to a slug.
    """
    return s.lower().replace(" ", "_")


@lrucache
def get_popolo() -> Popolo:
    return Popolo.from_path(memberdata_path / "people.json")


def get_person_from_lords_member(
    member: Member, register_date: datetime.date
) -> PersonInfo:
    """
    Get the MySoc person ID and name from a Lords member using MNIS identifier.
    """
    popolo = get_popolo()

    try:
        # Use MNIS ID for matching - this is much more reliable than name matching
        person = popolo.persons.from_identifier(
            str(member.id), scheme=IdentifierScheme.MNIS
        )

        # Get person name for the register date
        member_names = person.names_on_date(register_date)
        if not member_names:
            raise ValueError(
                f"Could not find name for person {person.id} on date {register_date}"
            )

        member_name = member_names[0]
        return PersonInfo(person_id=person.id, person_name=member_name)

    except Exception as e:
        # If MNIS identifier matching fails, log and return None
        raise ValueError(
            f"Could not match Lords member {member.id} ({member.name_display_as}): {e}"
        )


def lords_interest_to_regmem_entry(interest: Interest) -> RegmemEntry:
    """
    Convert a Lords Interest to a RegmemEntry.
    These are structurally pretty similar. 
    """
    # Convert datetime objects to dates for the RegmemEntry model
    date_registered = interest.created_when.date() if interest.created_when else None

    date_updated = (
        interest.last_amended_when.date() if interest.last_amended_when else None
    )

    entry = RegmemEntry(
        info_type="entry",
        id=str(interest.id),
        content=interest.interest,
        date_registered=date_registered,
        date_updated=date_updated,
    )

    # Add any child interests as sub-entries
    for child_interest in interest.child_interests:
        sub_entry = lords_interest_to_regmem_entry(child_interest)
        sub_entry.info_type = "subentry"
        entry.sub_entries.append(sub_entry)

    return entry


def convert_lords_data_to_regmem(
    data: ItemCollection, register_date: datetime.date
) -> RegmemRegister:
    """
    Convert Lords ItemCollection data to RegmemRegister format.
    """
    register = RegmemRegister(
        chamber=Chamber.LORDS,
        published_date=register_date,
        persons=[],
        annotations=[
            RegmemAnnotation(
                author="mySociety",
                content="Converted from Lords API to universal format",
            )
        ],
    )

    for item in data:
        member = item.value.member

        try:
            # Get the MySoc person ID and name
            person_info = get_person_from_lords_member(member, register_date)
        except ValueError as e:
            # Skip if we can't match the person - error already logged in the function
            rich.print(str(e))
            continue

        # Create RegmemPerson
        regmem_person = RegmemPerson(
            person_id=person_info.person_id,
            person_name=person_info.person_name,
            language="en",
            chamber=Chamber.LORDS,
            published_date=register_date,
            categories=[],
        )

        # Process interest categories
        for category in item.value.interest_categories:
            regmem_category = RegmemCategory(
                category_id=str(category.id),
                category_name=category.name,
                entries=[],
            )

            # Process interests in this category
            for interest in category.interests:
                entry = lords_interest_to_regmem_entry(interest)
                regmem_category.entries.append(entry)

            if regmem_category.entries:  # Only add if there are entries
                regmem_person.categories.append(regmem_category)

        if regmem_person.categories:  # Only add if there are categories
            register.persons.append(regmem_person)

    return register


@dataclass
class LordsRegisterManager:
    parldata_dir: Path
    quiet: bool = False
    no_progress: bool = False

    def get_register_from_api(self) -> ItemCollection:
        """
        Get Lords register data from the API.
        """
        return ItemCollection.get_from_api()

    def json_storage_path(self, register_date: datetime.date) -> Path:
        """
        Get the path for storing the raw JSON data.
        """
        folder = self.parldata_dir / "scrapedjson" / "regmem_json"
        if not folder.exists():
            folder.mkdir(exist_ok=True, parents=True)
        return folder / f"lords_{register_date.isoformat()}.json"

    def get_register_date(self, data: ItemCollection) -> datetime.date:
        """
        Get the register date from the data (latest date of any entry).
        """
        latest_date = None

        for item in data:
            for category in item.value.interest_categories:
                for interest in category.interests:
                    dates_to_check = [
                        interest.created_when,
                        interest.last_amended_when,
                    ]

                    for date_val in dates_to_check:
                        if date_val:
                            if latest_date is None or date_val.date() > latest_date:
                                latest_date = date_val.date()

        return latest_date or datetime.date.today()

    def download_and_store_raw_data(self, force_refresh: bool = False) -> RegisterData:
        """
        Download Lords data from API and store as JSON.
        Returns RegisterData with the data and register date.
        """
        if not self.quiet:
            rich.print("Downloading Lords register data from API...")

        data = self.get_register_from_api()
        register_date = self.get_register_date(data)

        json_path = self.json_storage_path(register_date)

        if not json_path.exists() or force_refresh:
            if not self.quiet:
                rich.print(f"Storing raw data to {json_path}")
            data.to_path(json_path)
        else:
            if not self.quiet:
                rich.print(f"Raw data already exists at {json_path}")

        return RegisterData(data=data, register_date=register_date)

    def get_universal_register(self, register_date: datetime.date) -> RegmemRegister:
        """
        Get the register in universal MySoc validator format.
        """
        json_path = self.json_storage_path(register_date)

        if json_path.exists():
            data = ItemCollection.from_path(json_path)
        else:
            register_data = self.download_and_store_raw_data()
            data = register_data.data

        return convert_lords_data_to_regmem(data, register_date)

    def write_universal_regmem(self, force_refresh: bool = False, quiet: bool = False):
        """
        Write the register in universal format and XML.
        """
        register_data = self.download_and_store_raw_data(force_refresh=force_refresh)

        filename = f"lords-regmem-{register_data.register_date.isoformat()}.json"
        dest = json_folder / filename

        if not dest.exists() or force_refresh:
            if not quiet:
                rich.print(f"Converting to universal format: {dest}")

            if not json_folder.exists():
                json_folder.mkdir(exist_ok=True, parents=True)

            mysoc_register = self.get_universal_register(register_data.register_date)
            mysoc_register.to_path(dest)

            # Also write XML format
            write_register_to_xml(
                mysoc_register, xml_folder_name="regmem", force_refresh=force_refresh
            )
        else:
            if not quiet:
                rich.print(f"Already exists at {dest}")


def download_latest_register(
    force_refresh: bool = False, quiet: bool = False, no_progress: bool = False
):
    """
    Download the latest Lords register.
    """
    if not quiet:
        rich.print("Downloading latest Lords register")

    manager = LordsRegisterManager(
        parldata_dir=parldata_path,
        quiet=quiet,
        no_progress=no_progress,
    )
    manager.write_universal_regmem(force_refresh=force_refresh, quiet=quiet)


if __name__ == "__main__":
    download_latest_register()
