"""
Script to fetch all (current) committee information from UK Parliament.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional, Protocol

import httpx
from bs4 import BeautifulSoup
from mysoc_validator import Popolo
from mysoc_validator.models.popolo import IdentifierScheme
from pydantic import BaseModel, ConfigDict, Field, RootModel
from tqdm import tqdm

from pyscraper.committees.groups import MiniGroup, MiniGroupCollection, MiniMember
from pyscraper.regmem.funcs import parldata_path

committee_json_path = (
    parldata_path / "scrapedjson" / "committees" / "uk_committees.json"
)
groups_path = parldata_path / "scrapedjson" / "committees" / "uk_committees_groups.json"


class VerboseSettings:
    verbose = True


class ApiCallWithSkip(Protocol):
    """
    Typing protocol that committee_app_loop accepts a function
    with a skip parameter
    """

    def __call__(self, skip: int) -> dict[Any, Any]: ...


def committee_app_loop(func: ApiCallWithSkip):
    """
    Handle paging the Parliament committees API
    """
    items: list[dict[str, str]] = []
    skip = 0
    pbar = tqdm(total=None, leave=False, disable=not VerboseSettings.verbose)
    while True:
        batch = func(skip=skip)
        if not batch["items"]:
            break
        pbar.total = batch["totalResults"]
        items.extend(batch["items"])
        skip += len(batch["items"])
        pbar.update(len(batch["items"]))
    pbar.close()
    return items


def reduce_purpose_html(html: str) -> str:
    """
    Extracts and cleans sentences from HTML content.

    Args:
        html (str): The HTML content as a string.

    Returns:
        str: A plain text string with sentences separated by new lines.
    """
    soup = BeautifulSoup(html, "html.parser")
    sentences = []

    for p in soup.find_all("p"):
        text = p.get_text(strip=True)
        for sentence in text.split(". "):
            sentence = sentence.strip()
            if not sentence:
                continue
            if sentence.lower().startswith("you can follow the committee on"):
                continue
            if len(p.find_all("a")) == len(p.contents):  # Only contains links
                continue
            if not sentence.endswith("."):
                sentence += "."
            sentences.append(sentence)

    return "\n".join(sentences)


def to_camel(string: str) -> str:
    """Convert snake_case to camelCase."""
    parts = string.split("_")
    return parts[0] + "".join(word.capitalize() for word in parts[1:])


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,  # allow both snake_case and camelCase
    )


class RoleType(CamelModel):
    id: int
    name: str


class RoleDetails(CamelModel):
    id: int
    name: str
    role_type: RoleType
    is_chair: bool


class Role(CamelModel):
    start_date: datetime
    end_date: Optional[datetime]
    role: RoleDetails
    ex_officio: bool
    alternate: bool
    co_opted: bool


class MemberInfo(CamelModel):
    member_from: Optional[str] = None
    party: Optional[str] = None
    party_colour: Optional[str] = None
    mnis_id: int
    is_chair: bool
    list_as: str
    display_as: str
    full_title: str
    address_as: Optional[str]
    house: Optional[str] = None
    is_current: bool


class Member(CamelModel):
    is_lay_member: bool
    roles: List[Role]
    id: int
    person_id: Optional[int]
    name: str
    photo_url: str
    member_info: Optional[MemberInfo] = None

    def mnis_id(self):
        if self.member_info and self.member_info.mnis_id:
            return self.member_info.mnis_id


class Contact(CamelModel):
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    contact_disclaimer: Optional[str] = None


class Category(CamelModel):
    id: int
    name: str


class CommitteeType(CamelModel):
    id: int
    name: str
    committee_category: Category


class NameHistory(CamelModel):
    id: int
    committee_id: int
    name: str
    start_date: datetime
    end_date: Optional[datetime] = None


class Department(CamelModel):
    department_id: int
    name: str


class LeadHouse(CamelModel):
    is_commons: bool
    is_lords: bool


class Committee(CamelModel):
    id: int
    name: str
    house: str
    purpose: Optional[str] = None
    contact: Optional[Contact] = None
    parent_committee: Optional[Committee] = None
    sub_committees: Optional[List[Committee]] = None
    lead_house: Optional[LeadHouse] = None
    category: Optional[Category] = None
    committee_types: List[CommitteeType]
    show_on_website: bool
    website_legacy_url: Optional[str] = None
    website_legacy_redirect_enabled: bool
    start_date: datetime
    end_date: Optional[datetime] = None
    date_commons_appointed: Optional[datetime] = None
    date_lords_appointed: Optional[datetime] = None
    scrutinising_departments: List[Department] = []
    is_lead_committee: Optional[bool] = None
    name_history: List[NameHistory]
    members: List[Member] = Field(default_factory=list)

    def parl_url(self):
        return f"https://committees.parliament.uk/committee/{self.id}/"

    def expand(self):
        """
        Get the full committee information from the API
        """
        url = f"https://committees-api.parliament.uk/api/Committees/{self.id}?includeBanners=false&showOnWebsiteOnly=false"
        response = httpx.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()
        return Committee.model_validate(data).add_members()

    def add_members(self):
        """
        Fetch and add members to the committee.
        """

        def get_paged_list_of_members(skip=0):
            url = f"https://committees-api.parliament.uk/api/Committees/{self.id}/Members?MembershipStatus=Current&ShowOnWebsiteOnly=true&skip={skip}"
            response = httpx.get(url, timeout=30)
            response.raise_for_status()
            return response.json()

        data = committee_app_loop(get_paged_list_of_members)
        self.members = [Member.model_validate(item) for item in data]
        return self


class CommitteeList(RootModel[list[Committee]]):
    def expand(self):
        new_items = []

        for item in tqdm(self.root, disable=not VerboseSettings.verbose):
            expanded = item.expand()
            new_items.append(expanded)

        return CommitteeList(root=new_items)

    def __iter__(self):
        return iter(self.root)


def get_committee_all_items():
    def get_committees(skip=0):
        url = f"https://committees-api.parliament.uk/api/Committees?CommitteeStatus=Current&skip={skip}"
        response = httpx.get(url)
        response.raise_for_status()
        return response.json()

    committees = committee_app_loop(get_committees)

    committee_list = CommitteeList.model_validate(committees)

    committee_list = committee_list.expand()

    committee_json_path.parent.mkdir(parents=True, exist_ok=True)
    with open(committee_json_path, "w") as f:
        f.write(committee_list.model_dump_json(indent=2))


def convert_to_groups():
    """
    Convert to the reduced groups format
    """
    with committee_json_path.open("r") as f:
        committees = CommitteeList.model_validate_json(f.read())

    collection = MiniGroupCollection(root=[])

    popolo = Popolo.from_parlparse()

    def get_twfy_id(member: Member) -> Optional[str]:
        try:
            return popolo.persons.from_identifier(
                str(member.mnis_id()), scheme=IdentifierScheme.MNIS
            ).id
        except ValueError:
            return None

    for comm in committees:
        categories: list[str] = []

        if comm.category:
            categories.append(comm.category.name)

        if comm.committee_types:
            categories.append(comm.committee_types[0].name)

        group = MiniGroup(
            name=comm.name,
            description=reduce_purpose_html(comm.purpose) if comm.purpose else "",
            external_url=comm.parl_url(),
            group_type="committee",
            group_categories=categories,
            members=[
                MiniMember(
                    name=member.name,
                    twfy_id=get_twfy_id(member),
                    officer_role="Chair"
                    if member.member_info and member.member_info.is_chair
                    else None,
                    external_member=member.is_lay_member,
                    is_current=member.member_info.is_current
                    if member.member_info
                    else False,
                )
                for member in comm.members
            ],
        )
        collection.root.append(group)

    with open(groups_path, "w") as f:
        f.write(collection.model_dump_json(indent=2))


if __name__ == "__main__":
    get_committee_all_items()
    convert_to_groups()
