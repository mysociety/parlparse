import datetime
from dataclasses import dataclass
from functools import lru_cache as lrucache
from itertools import groupby
from pathlib import Path
from typing import Any, Literal, Optional

import requests
import rich
from mysoc_validator import Popolo
from mysoc_validator.models.consts import Chamber
from mysoc_validator.models.interests import (
    RegmemAnnotation,
    RegmemCategory,
    RegmemDetail,
    RegmemDetailGroup,
    RegmemEntry,
    RegmemPerson,
    RegmemRegister,
)
from mysoc_validator.models.popolo import IdentifierScheme
from mysoc_validator.models.xml_interests import Register
from pydantic import TypeAdapter
from tqdm import tqdm

from pyscraper.regmem.commons.api_models import (
    CommonsAPIFieldModel,
    CommonsAPIMember,
    CommonsAPIPublishedInterest,
    CommonsAPIPublishedRegister,
)
from pyscraper.regmem.funcs import memberdata_path, nice_name, parldata_path
from pyscraper.regmem.legacy_converter import (
    convert_legacy_to_register,
    write_register_to_xml,
)

REGISTER_BASE = "https://interests-api.parliament.uk/"
xml_folder = parldata_path / "scrapedxml" / "regmem"
json_folder = (
    parldata_path / "scrapedjson" / "universal_format_regmem" / Chamber.COMMONS
)


def slugify(s: str) -> str:
    """
    Convert a string to a slug.
    """
    return s.lower().replace(" ", "_")


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
) -> CommonsAPIPublishedInterest:
    url = REGISTER_BASE + f"api/v1/Interests/{interest_id}"
    item = requests.get(url).json()
    interest = CommonsAPIPublishedInterest.model_validate(item)
    return interest


def get_list_of_registers(
    quiet: bool = False, no_progress: bool = False
) -> list[CommonsAPIPublishedRegister]:
    url = REGISTER_BASE + "api/v1/Registers"
    items = recursive_fetch(url, quiet=quiet, no_progress=no_progress)
    registers = TypeAdapter(list[CommonsAPIPublishedRegister]).validate_python(items)
    return registers


def field_type_converter(their_field: str) -> str:
    lookup = {
        "Decimal": "decimal",
        "DateOnly": "date",
        "Int": "int",
        "Boolean": "boolean",
        "String": "string",
    }

    if their_field.endswith("[]"):
        return "container"

    return lookup.get(their_field, "string")


def api_field_to_universal_detail(field: CommonsAPIFieldModel) -> RegmemDetail:
    our_field = field_type_converter(field.type or "String")
    DetailType = RegmemDetail.parameterized_class_from_str(our_field)

    display_as = nice_name(field.name)
    slug = slugify(display_as)

    if field.values:
        # if there are subvalues here

        groups: list[RegmemDetailGroup] = []

        for subitem_list in field.values or []:
            items_to_add = RegmemDetailGroup()
            for item in subitem_list:
                items_to_add.append(api_field_to_universal_detail(item))
            groups.append(items_to_add)

        detail = RegmemDetail[list[RegmemDetailGroup]](
            display_as=display_as,
            slug=slug,
            description=field.description,
            type="container",
            value=groups,
        )

    else:
        detail = DetailType(
            display_as=display_as,
            slug=slug,
            description=field.description,
            type=our_field,
            value=field.value,
        )

    return detail


def api_interest_to_universal_regmem_item(
    api_interest: CommonsAPIPublishedInterest,
    entry_type: Literal["entry", "subentry"] = "entry",
) -> RegmemEntry:
    uni_interest = RegmemEntry(
        info_type=entry_type,
        id=str(api_interest.id),
        content=api_interest.summary,
        date_registered=api_interest.registration_date,
        date_updated=api_interest.last_updated_date,
        date_published=api_interest.published_date,
    )

    for field in api_interest.fields:
        if field.value or field.values:
            detail = api_field_to_universal_detail(field)
            uni_interest.details.append(detail)
            if detail.slug == "received_date":
                uni_interest.date_received = detail.value

    for child in api_interest.child_items:
        uni_interest.sub_entries.append(
            api_interest_to_universal_regmem_item(child, entry_type="subentry")
        )

    return uni_interest


def move_subitems_under_parent(
    interests: list[CommonsAPIPublishedInterest],
    wider_list: list[CommonsAPIPublishedInterest],
) -> list[CommonsAPIPublishedInterest]:
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
    interests: list[CommonsAPIPublishedInterest],
) -> list[CommonsAPIMember]:
    """
    Here we're converting a mixed list of interests for different people and categories
    into a hierarchy of members > categories > interests > details.
    """

    interests.sort(key=lambda x: x.member.id)

    members: list[CommonsAPIMember] = []

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
                        # if a duplicate, we want to dump the category 1 rather than 1.1 or 1.2.
                        if i.child_items and c.number != "1":
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
        interests = TypeAdapter(list[CommonsAPIPublishedInterest]).validate_python(
            items
        )
        return interests

    def json_storage_path(self):
        folder = self.parldata_dir / "scrapedjson" / "regmem_json"
        if not folder.exists():
            folder.mkdir(exist_ok=True, parents=True)
        return folder / f"commons_{self.register_id}.json"

    def store_interests(self, interests: list[CommonsAPIPublishedInterest]):
        json = TypeAdapter(list[CommonsAPIPublishedInterest]).dump_json(
            interests, indent=2
        )
        self.json_storage_path().write_bytes(json)

    def load_interests(self):
        json = self.json_storage_path().read_text()
        interests = TypeAdapter(list[CommonsAPIPublishedInterest]).validate_json(json)
        return interests

    def get_register(
        self, *, force_refresh: bool = False
    ) -> list[CommonsAPIPublishedInterest]:
        """
        Use local backup if available, otherwise fetch from API
        """
        path = self.json_storage_path()
        if path.exists() and not force_refresh:
            return self.load_interests()
        interests = self.get_register_from_api()
        self.store_interests(interests)
        return interests

    def get_restacked_register(self) -> list[CommonsAPIMember]:
        """
        we start off with a big list of interests.
        We want to have this as a hierarchy of members > categories > interests > subinterests
        that matches what we do in the XML.
        """
        interests = self.get_register()
        return convert_list_to_regmem_hierarchy(interests)

    def get_universal_register(self, date: datetime.date) -> RegmemRegister:
        """
        Fetch the final register object that can be saved to xml
        """
        interests = self.get_restacked_register()

        popolo = get_popolo()

        uni = RegmemRegister(
            chamber=Chamber.COMMONS,
            published_date=date,
        )

        uni.annotations.append(
            RegmemAnnotation(
                author="mySociety",
                content="Converted from Commons API to universal format",
            )
        )

        for api_member in interests:
            person = popolo.persons.from_identifier(
                f"{api_member.id}", scheme=IdentifierScheme.MNIS
            )
            member_name = person.names_on_date(self.register_date)
            if not member_name:
                raise ValueError(f"Could not find name for {person.id}")
            else:
                member_name = member_name[0]

            person_entry = RegmemPerson(
                person_id=person.id,
                person_name=member_name,
                language="en",
                chamber=Chamber.COMMONS,
                published_date=date,
                categories=[],
            )

            for api_category in api_member.categories:
                uni_cat = RegmemCategory(
                    category_id=api_category.number,
                    category_name=api_category.name or "",
                    entries=[],
                )

                for api_interest in api_category.interests:
                    uni_interest = api_interest_to_universal_regmem_item(api_interest)

                    uni_cat.entries.append(uni_interest)

                person_entry.categories.append(uni_cat)

            uni.persons.append(person_entry)

        return uni

    def write_universal_regmem(self, force_refresh: bool = False, quiet: bool = False):
        """
        Write the register to the parldata directory
        """

        if not json_folder.exists():
            json_folder.mkdir(exist_ok=True, parents=True)

        filename = f"commons-regmem-{self.register_date.isoformat()}.json"
        dest = json_folder / filename
        if not dest.exists() or force_refresh:
            rich.print(f"Downloading to {dest}")
            mysoc_register = self.get_universal_register(self.register_date)
            mysoc_register.to_path(json_folder / filename)
            write_register_to_xml(
                mysoc_register, xml_folder_name="regmem", force_refresh=force_refresh
            )
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
    manager.write_universal_regmem(force_refresh=force_refresh, quiet=quiet)


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


def convert_xml_folder():
    """
    Intended to run once to convert all the old-style xml to new-style json.
    This is needed to have register information for old MPs
    loaded into the database in the same way.
    """

    if not json_folder.exists():
        json_folder.mkdir(exist_ok=True, parents=True)

    starting_point = "regmem2015-06-08.xml"
    for xml_file in xml_folder.glob("*.xml"):
        # if xml_file is less than starting_point, skip
        if xml_file.name < starting_point:
            continue
        print(xml_file)
        date = datetime.date.fromisoformat(xml_file.stem[6:])
        dest_filename = f"commons-regmem-{date.isoformat()}.json"
        dest = json_folder / dest_filename
        if not dest.exists():
            register = Register.from_xml_path(xml_file)
            legacy_register = convert_legacy_to_register(
                register, chamber=Chamber.COMMONS, published_date=date
            )
            legacy_register.to_path(dest)


if __name__ == "__main__":
    download_all_registers()
