import re
import time
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


class ScraperError(Exception):
    """
    Custom exception for scraper errors.
    """

    pass


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

    max_attempts = 3
    current_attempt = 0

    while current_attempt < max_attempts:
        try:
            items = pd.read_html(content)
            break  # If successful, exit the loop
        except ValueError as e:
            if "No tables found" in str(e):
                # If this is the first attempt and it failed with "No tables found",
                # wait 10 seconds and retry
                print(
                    f"No tables found for MS ID {ms_id} in {lang} language. Retrying in 10 seconds..."
                )
                current_attempt += 1
                if current_attempt == max_attempts:
                    # If this is the last attempt, raise the error
                    print(
                        f"Failed to find tables for MS ID {ms_id} in {lang} language after {max_attempts} attempts."
                    )
                    raise ScraperError(
                        f"Failed to find tables for MS ID {ms_id} in {lang} language after {max_attempts} attempts."
                    )
                time.sleep(10)
                # Get fresh content for the retry
                content = requests.get(url, headers=headers).content

            else:
                # Another error
                raise e

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

    # Extract category metadata from HTML tables and data from pandas tables.
    tables = soup.find_all("table")

    categories: list[RegmemCategory] = []

    for table_soup, table in zip_longest(tables, items):
        if table_soup is None or table is None:
            continue

        # Senedd format example
        # <table class="mgInterestsTable" ...>
        #   <caption>Remunerated Employment, Directorships etc.</caption>
        #   <tr><th scope="col">Category 1</th></tr>
        #   <tr><td>Entry in respect of: ...</td></tr>
        # </table>
        # Category name from <caption>
        # Category id from the <th> text.
        caption = table_soup.caption.get_text(strip=True) if table_soup.caption else ""
        header = table_soup.find("th")
        category_heading = header.get_text(strip=True) if header else ""

        category_name = caption.strip().removesuffix(":")
        category_heading = category_heading.strip()
        match = re.search(r"(\d+)", category_heading)
        if not match:
            raise ValueError(
                f"Could not parse category id from heading '{category_heading}'"
            )
        category_id = int(match.group(1))

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
                    entry.content = f"{summary_options[0]} ({in_respect_of})"
                else:
                    entry.content = summary_options[0]
            elif len(summary_options) > 1:
                entry.content = "|".join(
                    f"{detail.display_as}: {detail.value}" for detail in entry.details
                )
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

    if not ms_ids:
        if not quiet:
            print("No current Senedd members found.")
        return

    try:
        person_entries = [
            get_ms_details(ms_id, lang=lang)
            for ms_id in tqdm(ms_ids, disable=quiet or no_progress)
        ]
    except ScraperError as e:
        print(f"Error scraping MS details: {e}")
        return
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
