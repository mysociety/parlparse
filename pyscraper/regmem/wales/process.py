from datetime import datetime
from itertools import zip_longest
from typing import Literal

import pandas as pd
import requests
from bs4 import BeautifulSoup
from mysoc_validator.models.consts import Chamber
from mysoc_validator.models.interests import (
    RegmemCategory,
    RegmemDetail,
    RegmemDetailGroup,
    RegmemEntry,
    RegmemPerson,
    RegmemRegister,
)
from tqdm import tqdm

from pyscraper.regmem.funcs import get_popolo, parldata_path
from pyscraper.regmem.legacy_converter import write_register_to_xml


def welsh_to_english_months(date_str: str) -> str:
    """
    Quick patch to help get the current date from the Welsh version of the register.
    """
    lookup = {
        "Ionawr": "January",
        "Chwefror": "February",
        "Mawrth": "March",
        "Ebrill": "April",
        "Mai": "May",
        "Mehefin": "June",
        "Gorffennaf": "July",
        "Awst": "August",
        "Medi": "September",
        "Hydref": "October",
        "Tachwedd": "November",
        "Rhagfyr": "December",
    }
    for welsh, english in lookup.items():
        date_str = date_str.replace(welsh, english)
    return date_str


def get_current_ms_ids() -> list[int]:
    """
    Get the IDs of MSs who have registered interests.
    """
    url = "https://senedd.wales/senedd-business/register-of-members-interests/"

    headers = {"User-Agent": "TWFY interests scraper"}
    content = requests.get(url, headers=headers).content

    # extract all links that start with https://business.senedd.wales/mgRofI.aspx?UID=
    soup = BeautifulSoup(content, "html.parser")

    ms_ids = [
        int(a["href"].split("UID=")[1])
        for a in soup.find_all("a")
        if "href" in a.attrs
        and a["href"].startswith("https://business.senedd.wales/mgRofI.aspx?UID=")
    ]

    ms_ids = list(set(ms_ids))
    ms_ids.sort()

    return ms_ids


def tidy_category(category: str) -> tuple[int, str]:
    # get id and name from '1. Category 1: Directorships' or similar
    # text is after the first :
    if ":" in category:
        category_id, category_name = category.split(":", 1)
        category_id = int(category_id.split(".")[0])
        category_name = category_name.strip()
    else:
        category_id, category_name = category.split(".", 1)
        category_id = int(category_id)
        category_name = category_name.strip()
    if category_name.endswith(":"):
        category_name = category_name[:-1]
    return category_id, category_name


def get_ms_details(ms_id: int, *, lang: Literal["en", "cy"] = "en") -> RegmemPerson:
    """
    Scrape the register of interests for a specific MS.
    """
    popolo = get_popolo()
    person = popolo.persons.from_identifier(str(ms_id), scheme="senedd")

    if lang == "en":
        url = f"https://business.senedd.wales/mgRofI.aspx?UID={ms_id}"
        date_trigger_phrase = "This register of interests was published on"
    elif lang == "cy":
        url = f"https://busnes.senedd.cymru/mgRofI.aspx?UID={ms_id}"
        date_trigger_phrase = "Cafodd y gofrestr o fuddiannau ei chyhoeddi ar"
    else:
        raise ValueError("lang must be 'en' or 'cy'")

    headers = {"User-Agent": "TWFY interests scraper"}
    content = requests.get(url, headers=headers).content

    items = pd.read_html(content)

    # Parse HTML with BeautifulSoup
    soup = BeautifulSoup(content, "html.parser")

    # get the name
    name = soup.find("h2", class_="mgSubTitleTxt")
    if not name:
        raise ValueError("Could not find name")
    name = name.get_text(strip=True)

    # find the date phrase to get the date it was last updated
    # for this member
    date_phrase = soup.find(
        "li", string=lambda x: str(x).startswith(date_trigger_phrase)
    )
    date_phrase = date_phrase.get_text(strip=True) if date_phrase else None
    if date_phrase:
        date_string = date_phrase.split(",")[1].strip()
        date_string = welsh_to_english_months(date_string)
        date = datetime.strptime(date_string, "%d %B %Y").date()
    else:
        raise ValueError("Could not find date")

    # Extract tables and captions
    # The captions are the category names
    # the tables include the data
    tables = soup.find_all("table")
    captions = [
        table.caption.get_text(strip=True) if table.caption else None
        for table in tables
    ]

    categories: list[RegmemCategory] = []

    for caption, table in zip_longest(captions, items):
        category_id, category_name = tidy_category(str(caption))
        category = RegmemCategory(
            category_id=str(category_id), category_name=category_name
        )
        for item in table.fillna("None").to_dict(orient="records"):
            entry = RegmemEntry(
                details=RegmemDetailGroup(
                    [RegmemDetail(display_as=str(k), value=v) for k, v in item.items()]
                )
            )
            summary_options: list[str] = []
            in_respect_of = ""
            for detail in entry.details:
                if detail.display_as in ["Cofnod ynghylch", "Entry in respect of"]:
                    if detail.value not in ["Member", "Aelod"]:
                        in_respect_of = detail.value
                else:
                    summary_options.append(str(detail.value))

            if len(summary_options) == 1:
                if in_respect_of:
                    summary_str = f"{summary_options[0]} ({in_respect_of})"
                else:
                    summary_str = summary_options[0]
                entry.content = summary_str
            details_none = [x.value for x in entry.details if x.value == "None"]
            if len(details_none) != len(entry.details):
                category.entries.append(entry)
        if category.entries:
            categories.append(category)

    person_entry = RegmemPerson(
        person_id=str(person.id),
        person_name=name,
        published_date=date,
        categories=categories,
        chamber=Chamber.SENEDD,
        language=lang,
    )

    return person_entry


def get_current_register(
    lang: Literal["en", "cy"] = "en",
    force_refresh: bool = False,
    quiet: bool = False,
    no_progress: bool = False,
):
    ms_ids = get_current_ms_ids()

    person_entries = [
        get_ms_details(ms_id, lang=lang)
        for ms_id in tqdm(ms_ids, disable=quiet or no_progress)
    ]
    latest_date = [x.published_date for x in person_entries]
    published_date = max(latest_date)

    register = RegmemRegister(
        chamber=Chamber.SENEDD,
        language=lang,
        published_date=published_date,
        persons=person_entries,
    )

    dest_folder = (
        parldata_path / "scrapedjson" / "universal_format_regmem" / "senedd" / lang
    )
    dest_folder.mkdir(parents=True, exist_ok=True)

    dest_path = dest_folder / f"senedd-regmem{published_date.isoformat()}.json"

    if not dest_path.exists() or force_refresh:
        register.to_path(dest_path)
    write_register_to_xml(
        register, xml_folder_name=f"regmem-senedd-{lang}", force_refresh=force_refresh
    )


def get_current_bilingual(
    force_refresh: bool = False, quiet: bool = False, no_progress: bool = False
):
    """
    Get the current register in both English and Welsh.
    """
    get_current_register(
        lang="en", force_refresh=force_refresh, quiet=quiet, no_progress=no_progress
    )
    get_current_register(
        lang="cy", force_refresh=force_refresh, quiet=quiet, no_progress=no_progress
    )


if __name__ == "__main__":
    get_current_bilingual(force_refresh=True)
