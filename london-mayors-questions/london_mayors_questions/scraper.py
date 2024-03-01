"""
Scraping function to retrieve information from the London Mayors Questions website
"""

from __future__ import annotations

import datetime
import time
from pathlib import Path
from typing import List, Optional, Union

import pandas as pd
import requests
import requests_cache
from bs4 import BeautifulSoup, NavigableString, Tag
from rich import print
from tqdm import tqdm

from .models import QuestionPage

# Set up the requests cache
cache_path = Path(__file__).resolve().parent / "cache"
requests_cache.install_cache(str(cache_path), expire_after=60 * 60 * 12)  # type: ignore


def just_tag(item: Union[Tag, NavigableString, None]) -> Tag:
    """
    Helper to ensure tags for typing purposes
    """
    if isinstance(item, Tag):
        return item
    else:
        raise ValueError(f"Expected a Tag, got {type(item)}")


def get_question_page(slug: str) -> QuestionPage:
    """
    Get the details of the question and the answer from the slug
    """
    tqdm.write(slug)
    base_url = "https://www.london.gov.uk/who-we-are/what-london-assembly-does/questions-mayor/find-an-answer/"

    url = f"{base_url}{slug}"

    # fetch ur
    response = requests.get(url)

    soup = BeautifulSoup(response.text, "lxml")

    # get the table <table class="styled-table">
    table = just_tag(soup.find("table", class_="styled-table"))

    # convert to pandas table
    df = pd.read_html(str(table))[0]
    # strip the final colon from each entry in the first column
    df.iloc[:, 0] = df.iloc[:, 0].str.strip(":")

    # make the label column snake_case and lowercase
    df["Label"] = df.iloc[:, 0].str.lower().str.replace(" ", "_")
    question_details = df.set_index("Label").to_dict()["Content"]

    # position the soup at the section-title to get the answers
    section_title = just_tag(soup.find("div", class_="section-title"))

    question_title = just_tag(
        section_title.find_next_sibling("h3", class_="page-section")
    ).text.strip()
    question_text = just_tag(
        section_title.find_next_sibling("div", class_="rich-text")
    ).text.strip()

    question_obj = QuestionPage(
        **question_details,
        slug=slug,
        title=question_title,
        question_text=question_text,
        url=url,
    )

    # get the answers

    # get the h2 element with the id answer
    answer = soup.find("h2", id="answer")

    # sometimes there isn't an asnwer yet, just move on if so
    if answer is not None:
        # get this elements's parent
        answer_parent = just_tag(answer.parent)

        # get the next u-space-y-7
        answer_content = just_tag(
            answer_parent.find_next_sibling("div", class_="u-space-y-7")
        )

        for i, answer in enumerate(
            answer_content.find_all("div", class_="u-space-y-5")
        ):
            text = answer.text.strip()
            # first line contains the date in the format 'Date:  Tuesday 20 December 2022'
            date = text.splitlines()[0].split(":")[-1].strip()
            # convert this to utc string
            date = pd.to_datetime(date).to_pydatetime()
            # get html version of answer
            html_version = str(answer)
            # the rest of the text is the answer
            answer = html_version.splitlines()[1:]

            # remove lines that start with <span <div </div
            answer = [
                x
                for x in answer
                if not x.startswith("<span")
                and not x.startswith("<div")
                and not x.startswith("</div")
            ]

            # within each line remove any remaining opening and closing divs
            answer = [x.replace("<div>", "").replace("</div>", "") for x in answer]

            question_obj.add_answer(response=answer, date=date)

    return question_obj


def fetch_slugs(
    start_date: datetime.datetime,
    end_date: datetime.datetime,
    limit: Optional[int] = None,
) -> List[str]:
    """
    Fetch the slugs for all questions between two dates from the search page
    paginate through results
    """
    start_date_str = start_date.strftime("%d-%m-%Y")
    end_date_str = end_date.strftime("%d-%m-%Y")
    print(f"[blue] Fetching between {start_date_str} and {end_date_str} [/blue]")
    # get the page
    all_slugs = []
    page_slugs = []
    page = 0
    while page == 0 or len(page_slugs) == 10:
        if page > 0:
            time.sleep(5)
        url = f"https://www.london.gov.uk/who-we-are/what-london-assembly-does/questions-mayor/find-an-answer?date_from={start_date}&date_to={end_date}&question_text=&sort_by=date&sort_order=ASC&page={page}"
        # print(url)
        print(f"Fetching between {start_date_str} and {end_date_str} (page {page})")
        # fetch the page with a longer timeout because sometimes we're warming up the search page
        response = requests.get(url, timeout=60)
        soup = BeautifulSoup(response.text, "lxml")
        # make a list of all links on the page
        links = soup.find_all("a")

        # restrict to those that match this general pattern
        # who-we-are/what-london-assembly-does/questions-mayor/find-an-answer/[slug]
        slugs = [
            link.get("href").split("/")[-1]
            for link in links
            if link.get("href").startswith(
                "/who-we-are/what-london-assembly-does/questions-mayor/find-an-answer"
            )
        ]

        # discard any with a ?
        page_slugs = [slug for slug in slugs if "?" not in slug]
        for slug in page_slugs:
            print(f"Found [green]{slug}[/green]")
        all_slugs.extend(page_slugs)
        page += 1
        if limit is not None and len(all_slugs) >= limit:
            break

    return all_slugs
