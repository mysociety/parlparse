import datetime
from functools import lru_cache
from io import StringIO
from typing import Optional

import pandas as pd
import requests
from bs4 import BeautifulSoup
from mysoc_validator.models.consts import Chamber
from mysoc_validator.models.interests import (
    RegmemCategory,
    RegmemDetail,
    RegmemEntry,
    RegmemPerson,
    RegmemRegister,
)
from pydantic import BaseModel
from tqdm import tqdm

from pyscraper.regmem.funcs import parldata_path


class AssemblyMember(BaseModel):
    name: str
    slug: str
    url: str
    term_start_date: Optional[datetime.date]
    political_group: Optional[str]
    constituency: Optional[str]
    portrait_image: str


class LondonRegisters:
    def __init__(self, member: AssemblyMember):
        self.member = member
        self.type = type

    def get_current_person_entry(self):
        roi, roi_date = self.get_roi()
        gifts = self.get_gifts()

        if not roi_date and len(roi) > 1:
            raise ValueError(
                f"Could not find date for register of interests for {self.member.name}"
            )

        if gifts:
            all_categories = [gifts] + roi
        else:
            all_categories = roi

        if all_categories and not roi_date:
            roi_date = max(
                [
                    x.entries[0].date_registered or datetime.datetime.min.date()
                    for x in all_categories
                ]
            )

        if not roi_date:
            return None

        # when relevent people are in popolo - need to do the lookup here.

        return RegmemPerson(
            chamber=Chamber.LONDON,
            language="en",
            person_id="0",
            published_date=roi_date,
            person_name=self.member.name,
            categories=all_categories,
        )

    def get_roi(self):
        roi_end = "register-of-interests"

        full_url = f"{self.member.url}/{roi_end}"

        content = requests.get(full_url).text

        soup = BeautifulSoup(content, "html.parser")

        date = soup.find("time")
        if date:
            # get datetime timestamp and get date obj
            update_date = datetime.datetime.fromisoformat(date["datetime"]).date()
        else:
            update_date = None

        found_items = {}

        for section in soup.find_all("div", class_="page-section"):
            header = section.find("h2")
            rich_text = section.find("div", class_="rich-text")

            if rich_text:
                # iterate through children of rich_text looking for <p> and <ul>
                current_category = None
                current_items = []
                for child in rich_text.children:
                    if child.name == "p":
                        if current_category:
                            found_items[current_category] = current_items
                            current_items = []
                        current_category = child.text
                    if child.name == "ul":
                        for li in child.find_all("li"):
                            current_items.append(li.text)
                if current_category:
                    found_items[current_category] = current_items

        categories = []
        for category_str, items in found_items.items():
            if not items:
                continue
            cat_id = category_str.split(".")[0]
            category = RegmemCategory(
                category_name=category_str,
                category_id=cat_id,
                entries=[RegmemEntry(content=x) for x in items],
            )

            categories.append(category)

        return categories, update_date

    def get_gifts(self) -> Optional[RegmemCategory]:
        gift_end = "gifts-hospitality"

        full_url = f"{self.member.url}/{gift_end}"

        content = requests.get(full_url).text
        try:
            dfs = pd.read_html(StringIO(content))
        except ValueError:
            return None

        df = dfs[0]
        results: list[RegmemEntry] = []

        for df in dfs:
            entries = df.to_dict(orient="records")

            for raw_entry in entries:
                entry = RegmemEntry(
                    content=raw_entry["Details"],
                    date_received=datetime.datetime.strptime(
                        raw_entry["Date gifted"], "%d %B %Y"
                    ).date(),
                )
                entry.details.extend(
                    [
                        RegmemDetail(display_as=str(x), value=y)
                        for x, y in raw_entry.items()
                        if x not in ["Details", "Date gifted"]
                    ]
                )
                results.append(entry)

        return RegmemCategory(
            category_id="0", category_name="Gifts and Hospitality", entries=results
        )


@lru_cache
def get_assembly_members():
    url = "https://www.london.gov.uk/who-we-are/what-london-assembly-does/london-assembly-members"
    return get_london_people(url)


@lru_cache
def get_mayor_people():
    url = "https://www.london.gov.uk/who-we-are/what-mayor-does/mayor-and-his-team"
    return get_london_people(url)


def get_london_people(people_url: str):
    content = requests.get(people_url).text

    soup = BeautifulSoup(content, "html.parser")
    # iterate through all a elements and grab ones that start with href /who-we-are/what-london-assembly-does/london-assembly-members/

    a = soup.find_all("a", href=True)

    members = []

    for div in soup.find_all("div", class_="card"):
        name = None
        slug = None
        url = None

        a = div.find_all("a", href=True)

        for link in a:
            if ("https://www.london.gov.uk" + link["href"]).startswith(people_url):
                name = link.text.strip()
                slug = link["href"].split("/")[-1]
                url = link["href"]
        if not name or not slug or not url:
            raise ValueError("Could not find name, slug, or url")

        start_date = div.find("time")
        if start_date:
            start_date = datetime.datetime.fromisoformat(start_date["datetime"]).date()
        else:
            start_date = None

        political_group = div.find(
            "div", class_="field--name-field-c-p-political-group"
        )
        if political_group:
            political_group = political_group.text.strip()
        else:
            political_group = None

        constituency = div.find("div", class_="field--name-field-c-p-constituency")
        if constituency:
            constituency = constituency.text.strip()
        else:
            constituency = None

        img = div.find("img")
        if img:
            img = img["src"]
        else:
            raise ValueError("Could not find image")

        members.append(
            AssemblyMember(
                name=name,
                slug=slug,
                url="https://www.london.gov.uk" + url,
                term_start_date=start_date,
                political_group=political_group,
                constituency=constituency,
                portrait_image="https://www.london.gov.uk" + img,
            )
        )

    return members


def get_current_registry(quiet: bool = False):
    all_people = []
    for member in tqdm(get_assembly_members() + get_mayor_people(), disable=quiet):
        reg = LondonRegisters(member)
        person = reg.get_current_person_entry()
        if person:
            all_people.append(person)

    last_update_date = max([x.published_date for x in all_people])

    return RegmemRegister(
        chamber=Chamber.LONDON, published_date=last_update_date, persons=all_people
    )


def write_register(force_refresh: bool = False, quiet: bool = False):
    register = get_current_registry(quiet=quiet)

    # remove gifts and hospitality a year before the last update

    if not register.published_date:
        raise ValueError("Expects a global published_date")

    for person in register.persons:
        for category in person.categories:
            if category.category_name == "Gifts and Hospitality":
                category.entries = [
                    x
                    for x in category.entries
                    if not x.date_received
                    or x.date_received
                    > register.published_date - datetime.timedelta(days=365)
                ]

    dest_folder = (
        parldata_path / "scrapedjson" / "universal_format_regmem" / Chamber.LONDON
    )

    if not dest_folder.exists():
        dest_folder.mkdir(exist_ok=True, parents=True)

    dest_path = dest_folder / f"london-regmem{register.published_date.isoformat()}.json"

    if not dest_path.exists() or force_refresh:
        register.to_path(dest_path)
        # Enable when we have valid twfy ids
        # write_register_to_xml(
        #    register, xml_folder_name="regmem-london", force_refresh=force_refresh
        # )


if __name__ == "__main__":
    write_register(force_refresh=True)
