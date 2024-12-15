import datetime
from dataclasses import dataclass
from functools import lru_cache as lrucache
from itertools import groupby
from pathlib import Path
from typing import Any, Optional

import requests
import rich
from mysoc_validator import Popolo
from mysoc_validator.models.interests import (
    Category,
    Item,
    PersonEntry,
    Record,
    Register,
)
from mysoc_validator.models.popolo import IdentifierScheme
from mysoc_validator.models.xml_base import MixedContentHolder
from pydantic import TypeAdapter
from tqdm import tqdm

from pyscraper.regmem.commons.api_models import (
    Member,
    PublishedCategory,
    PublishedInterest,
    PublishedRegister,
)


def get_higher_path(folder_name: str) -> Path:
    current_level = Path.cwd()
    allowed_levels = 3
    for i in range(allowed_levels):
        if (current_level / folder_name).exists():
            return current_level / folder_name
        current_level = current_level.parent
    return Path.home() / folder_name


parldata_path = get_higher_path("parldata")
memberdata_path = get_higher_path("members")

REGISTER_BASE = "https://interests-api.parliament.uk/"


@lrucache
def get_popolo() -> Popolo:
    return Popolo.from_path(memberdata_path / "people.json")


def recursive_fetch(
    url: str,
    params: Optional[dict[str, Any]] = None,
    quiet: bool = False,
    no_progress: bool = False,
):
    """
    Meta API handler
    """
    take = 20
    skip = 0
    target_items = 0
    all_items = []
    continue_fetching = True

    if take > 20:
        raise ValueError(
            "Take must be less than or equal to 20 - API limit annoyingly."
        )

    bar = tqdm(desc="Fetching ", unit="items", disable=quiet or no_progress)

    while continue_fetching:
        send_params = {"Take": take, "Skip": skip}
        if params:
            send_params.update(params)
        response = requests.get(url, send_params)
        response.raise_for_status()
        data = response.json()
        target_items = data["totalResults"]
        all_items.extend(data["items"])
        bar.total = target_items
        bar.update(take)
        skip += take
        if skip >= target_items:
            continue_fetching = False

    if len(all_items) != target_items:
        raise ValueError(f"Expected {target_items} items, got {len(all_items)}")

    return all_items


def get_single_item(
    interest_id: int,
) -> PublishedInterest:
    url = REGISTER_BASE + f"api/v1/Interests/{interest_id}"
    item = requests.get(url).json()
    interest = PublishedInterest.model_validate(item)
    return interest


def get_list_of_registers(
    quiet: bool = False, no_progress: bool = False
) -> list[PublishedRegister]:
    url = REGISTER_BASE + "api/v1/Registers"
    items = recursive_fetch(url, quiet=quiet, no_progress=no_progress)
    registers = TypeAdapter(list[PublishedRegister]).validate_python(items)
    return registers


def move_subitems_under_parent(
    interests: list[PublishedInterest], wider_list: list[PublishedInterest]
) -> list[PublishedInterest]:
    """
    Return top-level interests with child interests stored as subinterests.

    The problem we're solving here is while we just get a list from the API
    There is actually some items with hierarchy and 'parent' interests.
    This is for "I have been paid by the Guardian (parent interest with org details)]
    for article a, b, c (child interests with dates)."

    We don't want to display 'Guardian', other unrelated items, then "I wrote an article" - we want to
    bring these together.

    The end result here is to return top level interests, with any subinterests linked under them.

    Because the same payer may apply to 1.1 or 1.2 - these sometimes sit in '1'.
    This means that when you get the list of items under a category (as this function expects),
    you might not have access to the parent item.

    The wider lookup is solving this - we're passing in the full list of items if we need to find a parent.

    This means we might duplicate the same parent_interest across 1.1 and 1.2, but that's fine.

    """
    all_item_ids = []

    # add all top level items to parent_items
    parent_items = {x.id: x for x in interests if x.parent_interest_id is None}

    wider_lookup = {x.id: x for x in wider_list}
    all_item_ids.extend(parent_items.keys())

    # gather child items into parent items
    for interest in interests:
        if interest.parent_interest_id is not None:
            if interest.parent_interest_id not in parent_items:
                try:
                    parent_interest = wider_lookup[interest.parent_interest_id]
                except KeyError:
                    # for some reason this isn't in the register download *at all*
                    parent_interest = get_single_item(interest.parent_interest_id)
                parent_items[parent_interest.id] = parent_interest
                all_item_ids.append(parent_interest.id)
            parent = parent_items[interest.parent_interest_id]
            parent.child_items.append(interest)
            all_item_ids.append(interest.id)

    for interest in interests:
        if interest.id not in all_item_ids:
            raise ValueError(f"Interest {interest.id} not moved across")

    return list(parent_items.values())


def convert_list_to_regmem_hierarchy(
    interests: list[PublishedInterest],
) -> list[Member]:
    """
    Here we're converting a mixed list of interests for different people and categories
    into a hierarchy of members > categories > interests > subinterests.

    """

    interests.sort(key=lambda x: x.member.id)

    members: list[Member] = []

    for _, member_interests in groupby(interests, key=lambda x: x.member.id):
        list_of_member_interests = list(member_interests)
        member = list_of_member_interests[0].member

        list_of_member_interests.sort(key=lambda x: x.category.id)

        categories = []

        for _, category_interests in groupby(
            list_of_member_interests, key=lambda x: x.category.id
        ):
            list_of_category_interests = list(category_interests)
            category = list_of_category_interests[0].category

            category.interests = move_subitems_under_parent(
                list_of_category_interests, wider_list=list_of_member_interests
            )

            categories.append(category)

        member.categories = categories

        members.append(member)

    members.sort(key=lambda x: x.id)

    # given we pull in parent interests when not in the category, we need to check we haven't duplicated

    existing_ids = set()
    duplicate_ids = set()

    for m in members:
        for c in m.categories:
            for i in c.interests:
                if i.id in existing_ids:
                    duplicate_ids.add(i.id)
                existing_ids.add(i.id)

    if duplicate_ids:
        # we want to delete items that have no children - as these are better expressed in other places
        # otherwise we're fine with duplicates top-level items because
        # it adds the correct context to items in multiple categories.

        for m in members:
            for c in m.categories:
                n_interests = []
                for i in c.interests:
                    if i.id in duplicate_ids:
                        if i.child_items:
                            n_interests.append(i)
                    else:
                        n_interests.append(i)
                c.interests = n_interests

    return members


@dataclass
class RegisterManager:
    register_id: int
    register_date: datetime.date
    parldata_dir: Path
    quiet: bool = False
    no_progress: bool = False

    def get_register_from_api(self):
        url = REGISTER_BASE + "api/v1/Interests/"
        items = recursive_fetch(
            url,
            params={"RegisterId": self.register_id},
            quiet=self.quiet,
            no_progress=self.no_progress,
        )
        interests = TypeAdapter(list[PublishedInterest]).validate_python(items)
        return interests

    def json_storage_path(self):
        folder = self.parldata_dir / "scrapedjson" / "regmem_json"
        if not folder.exists():
            folder.mkdir(exist_ok=True, parents=True)
        return folder / f"commons_{self.register_id}.json"

    def store_interests(self, interests: list[PublishedInterest]):
        json = TypeAdapter(list[PublishedInterest]).dump_json(interests, indent=2)
        self.json_storage_path().write_bytes(json)

    def load_interests(self):
        json = self.json_storage_path().read_text()
        interests = TypeAdapter(list[PublishedInterest]).validate_json(json)
        return interests

    def get_register(self, *, force_refresh: bool = False) -> list[PublishedInterest]:
        """
        Use local backup if available, otherwise fetch from API
        """
        path = self.json_storage_path()
        if path.exists() and not force_refresh:
            return self.load_interests()
        interests = self.get_register_from_api()
        self.store_interests(interests)
        return interests

    def get_restacked_register(self) -> list[Member]:
        """
        we start off with a big list of interests.
        We want to have this as a hierarchy of members > categories > interests > subinterests
        that matches what we do in the XML.
        """
        interests = self.get_register()
        return convert_list_to_regmem_hierarchy(interests)

    def get_mysoc_register(self) -> Register:
        """
        Fetch the final register object that can be saved to xml
        """
        interests = self.get_restacked_register()
        return self.stacked_register_to_mysoc(interests)

    def api_interest_to_mysoc_item(self, interest: PublishedInterest) -> Item:
        """
        Take a record object from the API and convert it to a Record object for parlparse.
        """
        text = interest.to_html()
        content = MixedContentHolder(raw=text, text="")
        return Item(contents=content, **{"class": "interest"})

    def api_category_to_mysoc_category(self, category: PublishedCategory) -> Category:
        """
        Take a category object from the API and convert it to a Category object for parlparse.
        """
        return Category(
            type=str(category.number),
            name=str(category.name),
            records=[
                Record(
                    items=[
                        self.api_interest_to_mysoc_item(x) for x in category.interests
                    ]
                )
            ],
        )

    def api_member_to_mysoc_person_entry(self, member: Member) -> PersonEntry:
        """
        Take a member object from the API and convert it to a PersonEntry object.
        """
        popolo = get_popolo()

        person = popolo.persons.from_identifier(
            f"{member.id}", scheme=IdentifierScheme.MNIS
        )
        member_name = person.names_on_date(self.register_date)
        if not member_name:
            raise ValueError(f"Could not find name for {person.id}")
        else:
            member_name = member_name[0]

        member.categories.sort(key=lambda x: x.number)

        categories = [self.api_category_to_mysoc_category(x) for x in member.categories]

        # given we pull in parent interests when not in the category, we need to check we haven't duplicated

        return PersonEntry(
            person_id=person.id,
            membername=member_name,
            date=self.register_date,
            record=None,
            categories=categories,
        )

    def stacked_register_to_mysoc(self, members: list[Member]) -> Register:
        """
        Take a list of members with categories and interests and convert them to a Register object.
        """
        persons = [self.api_member_to_mysoc_person_entry(x) for x in members]
        persons.sort(key=lambda x: x.person_id)

        return Register(tag="twfy", person_entries=persons)

    def write_mysoc_regmem(self, force_refresh: bool = False, quiet: bool = False):
        """
        Write the register to the parldata directory
        """

        dest_folder = self.parldata_dir / "scrapedxml" / "regmem"

        if not dest_folder.exists():
            dest_folder.mkdir(exist_ok=True, parents=True)

        filename = f"regmem{self.register_date.isoformat()}.xml"
        dest = dest_folder / filename
        if not dest.exists() or force_refresh:
            rich.print(f"Downloading to {dest}")
            mysoc_register = self.get_mysoc_register()
            mysoc_register.to_xml_path(dest_folder / filename)
        else:
            if not quiet:
                rich.print(f"Already exists at {dest}")


def download_register_from_id_and_date(
    register_id: int,
    date: datetime.date,
    force_refresh: bool = False,
    quiet: bool = False,
    no_progress: bool = False,
):
    if not quiet:
        rich.print(f"Downloading commons register {register_id} from {date}")
    manager = RegisterManager(
        register_id=register_id,
        register_date=date,
        parldata_dir=parldata_path,
        quiet=quiet,
        no_progress=no_progress,
    )
    manager.write_mysoc_regmem(force_refresh=force_refresh, quiet=quiet)


def download_register_from_date(
    date: datetime.date,
    force_refresh: bool = False,
    quiet: bool = False,
    no_progress: bool = False,
):
    for register in get_list_of_registers(quiet=quiet, no_progress=no_progress):
        if register.published_date == date:
            return download_register_from_id_and_date(
                register.id,
                register.published_date,
                force_refresh=force_refresh,
                quiet=quiet,
                no_progress=no_progress,
            )

    raise ValueError(f"No register found for {date}")


def download_latest_register(
    force_refresh: bool = False, quiet: bool = False, no_progress: bool = False
):
    registers = get_list_of_registers(quiet=quiet, no_progress=no_progress)
    latest = max(registers, key=lambda x: x.published_date)
    return download_register_from_id_and_date(
        latest.id,
        latest.published_date,
        force_refresh=force_refresh,
        quiet=quiet,
        no_progress=no_progress,
    )


def download_all_registers(
    force_refresh: bool = False, quiet: bool = False, no_progress: bool = False
):
    registers = get_list_of_registers(quiet=quiet, no_progress=no_progress)
    for register in registers:
        download_register_from_id_and_date(
            register.id,
            register.published_date,
            force_refresh=force_refresh,
            quiet=quiet,
            no_progress=no_progress,
        )


if __name__ == "__main__":
    download_all_registers()
