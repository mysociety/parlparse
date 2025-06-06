"""
Module for downloading the debates from the Scottish Parliament website.

This uses the search page to get a list of committees that have met on a given date or range.
Individual agenda items are then queried and dumped in an XML file in the cache directory.
One file per committee per day.

"""

from __future__ import annotations

import re
from itertools import groupby
from pathlib import Path
from typing import Iterator, NamedTuple
from urllib.parse import parse_qs, urlparse

import requests
from bs4 import BeautifulSoup
from lxml import etree

user_agent = (
    "Mozilla/5.0 (Ubuntu; X11; Linux i686; rv:9.0.1) Gecko/20100101 Firefox/9.0.1"
)

scot_prefix = "https://www.parliament.scot"
search_url = "/chamber-and-committees/official-report/search-what-was-said-in-parliament?msp=&committeeSelect=&qry=&dateSelect=custom&dtDateFrom={start_date}&dtDateTo={end_date}&showPlenary=true&ShowDebates=true&ShowFMQs=true&ShowGeneralQuestions=true&ShowPortfolioQuestions=true&ShowSPCBQuestions=true&ShowTopicalQuestions=true&ShowUrgentQuestions=true&showCommittee=true&page={page}"
item_url = "/chamber-and-committees/official-report/search-what-was-said-in-parliament/{slug}?meeting={id}&iob={iob}"
major_heading_url = "/chamber-and-committees/official-report/search-what-was-said-in-parliament/{slug}?meeting={id}"


def get_meeting_urls(start_date: str, end_date: str, page: int = 1):
    """
    Query the Scottish Parliament search page for a given date range to get all links for agenda meetings
    """
    date_url = scot_prefix + search_url.format(
        start_date=start_date, end_date=end_date, page=page
    )
    response = requests.get(date_url, headers={"User-Agent": user_agent})

    # extract all urls that contain /search-what-was-said-in-parliament/
    soup = BeautifulSoup(response.text, "html.parser")
    meeting_urls = [
        a["href"]
        for a in soup.find_all("a", href=True)
        if "/search-what-was-said-in-parliament/" in a["href"]
    ]

    # section headings
    heading_urls = [url for url in meeting_urls if "&iob=" not in url]
    heading_count = len(set(heading_urls))

    # discard any without a iob parameter
    meeting_urls = [url for url in meeting_urls if "&iob=" in url]

    # remove duplicates
    meeting_urls = sorted(list(set(meeting_urls)))
    return heading_count, meeting_urls


def get_debate_groupings(start_date: str, end_date: str) -> list[DebateGrouping]:
    """
    Query the search page and get the urls for the meetings in that date range
    """

    keep_fetching = True
    search_page = 1
    meeting_urls = []

    while keep_fetching:
        heading_count, page_result_urls = get_meeting_urls(
            start_date, end_date, search_page
        )
        meeting_urls.extend(page_result_urls)
        if len(page_result_urls) < 10:
            keep_fetching = False
        else:
            search_page += 1

    def get_committee_slug(url: str):
        return url.split("?")[0].split("/")[-1]

    groupings = []

    for g, items in groupby(meeting_urls, key=get_committee_slug):
        date = "-".join(reversed(g.split("-")[-3:]))
        url_ids = []
        url_iobs = []

        for item in items:
            # get the url parameters as dict
            parsed = parse_qs(urlparse(item).query)
            url_ids.append(int(parsed["meeting"][0]))
            url_iobs.append(int(parsed["iob"][0]))

        if len(set(url_ids)) > 1:
            raise ValueError("Multiple committee ids in grouping")

        groupings.append(
            DebateGrouping(
                date=date,
                committee_date_slug=g,
                committee_date_id=url_ids[0],
                items=url_iobs,
            )
        )

    return groupings


class DebateGrouping(NamedTuple):
    date: str
    committee_date_slug: str
    committee_date_id: int
    items: list[int]

    def urls(self) -> Iterator[str]:
        """
        Generator for the urls of the agenda items
        """
        for i in self.items:
            yield scot_prefix + item_url.format(
                slug=self.committee_date_slug, id=self.committee_date_id, iob=i
            )

    def get_debate_item_content(self, speech_id: str, url: str):
        """
        For each agenda item (they're on separate pages)
        Query the page, extract the header name and agenda item, and then
        the contents of the actual debate.
        We just save that to parse it later.
        """

        response = requests.get(url, headers={"User-Agent": user_agent})
        raw_html = response.text
        raw_html = re.sub(
            '(<p class="or-contribution-box">)(\s*<p )', r"\1</p>\2", raw_html
        )
        raw_html = re.sub(
            '(<p class="or-contribution-box">)(\s*<hr />\s*<p )', r"\1</p>\2", raw_html
        )
        soup = BeautifulSoup(raw_html, "html.parser")

        # first h1 is the heading, last h2 is the subheading
        heading = soup.find_all("h1")[0].text
        subheading = soup.find_all("h2")[-1].text

        # delete class share-float-right
        for div in soup.find_all("div", {"class": "share-float-right"}):
            div.decompose()

        # delete h3 u--mtop0 - the subheading caught above
        for h3 in soup.find_all("h2", {"class": "h3 u--mtop0"}):
            h3.decompose()

        # the last rich text div is the content
        speech = soup.find_all("div", {"class": "rich-text"})[-1]
        speech_tree = etree.fromstring(str(speech))

        # create a new tree, that has a agenda_item as the root
        # with the id, heading and subheading as attributes

        major_minor_id = f"a{self.committee_date_id}.{speech_id}"

        root = etree.Element(
            "agenda_item",
            id=major_minor_id,
            url=url,
            heading_title=heading,
            title=subheading,
        )

        # create raw_html element
        raw_html = etree.Element("raw_html")
        # transfer the contents of the speech tree to the new tree
        for child in speech_tree:
            raw_html.append(child)

        root.append(raw_html)

        return root

    def construct_xml(self) -> etree.Element:
        """
        Create the XML structure for storing all agenda items discussed
        by the committee on that day.
        """
        major_url = scot_prefix + major_heading_url.format(
            slug=self.committee_date_slug, id=self.committee_date_id
        )

        items = []

        for url in self.urls():
            items.append(self.get_debate_item_content(str(self.items[0]), url))

        # get major heading title
        heading_title = items[0].attrib["heading_title"]

        root = etree.Element(
            "committee",
            url=major_url,
            title=heading_title,
            date=self.date,
            committee=self.committee_date_slug,
            id=f"c{self.committee_date_id}.0",
        )

        for item in items:
            root.append(item)

        etree.indent(root, space="    ")

        return root

    def save_xml(self, cache_dir: Path, override: bool = False) -> Path:
        """
        Generated interim xml file and save it to the cache directory
        """
        filename = cache_dir / f"{self.date}-{self.committee_date_slug}.xml"
        if filename.exists() is False or override:
            xml = self.construct_xml()
            with filename.open("wb") as f:
                f.write(etree.tostring(xml))
        return filename


def fetch_debates_for_dates(
    start_date: str,
    end_date: str,
    cache_dir: Path,
    verbose: bool = False,
    override: bool = False,
):
    """
    Fetch debates across all chambers for a given date range
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    for grouping in get_debate_groupings(start_date, end_date):
        if verbose:
            print(f"Fetching debates for {grouping.committee_date_slug}")
        yield grouping.save_xml(cache_dir=cache_dir, override=override)
