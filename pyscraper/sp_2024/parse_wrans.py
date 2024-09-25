"""
This module contains tools to convert the unstructured HTML of the debates into structured XML.
This is not the TWFY style XML - but tries to retain all information from the original.
"""

from __future__ import annotations

import re
from pathlib import Path

from bs4 import BeautifulSoup, Tag

# HTML elements we accept moving from raw_html to parsed
acceptable_elements = [
    "a",
    "abbr",
    "acronym",
    "address",
    "b",
    "big",
    "blockquote",
    "br",
    "caption",
    "center",
    "cite",
    "col",
    "colgroup",
    "dd",
    "dir",
    "div",
    "dl",
    "dt",
    "em",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "i",
    "img",
    "li",
    "ol",
    "p",
    "pre",
    "q",
    "s",
    "small",
    "span",
    "strike",
    "strong",
    "sub",
    "sup",
    "table",
    "tbody",
    "td",
    "tfoot",
    "th",
    "thead",
    "title",
    "tr",
    "tt",
    "u",
    "ul",
    "timestamp",
]


def process_raw_html(raw_html: Tag, wrans_item_url: str) -> BeautifulSoup:
    """
    Given the question html, convert it to a structured xml format
    This isn't yet matching TWFY schema or using the right IDs.
    The goal is to make a structured file that's a bit easier to work with.
    """

    # Deal with timestamps that are not inside anything first
    raw_html = str(raw_html)
    soup = BeautifulSoup(raw_html, "html.parser")

    # convert a structure where there's a question with a question and a reply inside

    details = soup.find("ul")
    speaker_re = re.compile(
        r"Asked by:\s*([^,]*),\s*MSP for\s*([^,]*),(.*)", re.MULTILINE
    )
    responder_re = re.compile(r".*Answered by\s*(\w.*)\s*on", re.MULTILINE | re.DOTALL)
    lodged_re = re.compile(r"Date lodged:\s*(\d+ \w+ \d+)", re.MULTILINE)
    speaker = None
    seat = None
    party = None
    responder = None
    lodged = None

    parsed = soup.new_tag("parsed")

    for li in details.find_all("li"):
        text = li.text.strip()

        speaker_match = re.match(speaker_re, text)
        responder_match = re.match(responder_re, text)
        lodged_match = re.match(lodged_re, text)

        if speaker_match:
            speaker = speaker_match.group(1)
            seat = speaker_match.group(2)
            party = speaker_match.group(3)
        elif responder_match:
            responder = responder_match.group(1)
        elif lodged_match:
            lodged = lodged_match.group(1)

        li.decompose()

    for h in soup.find_all("h3"):
        div = h.find_next("div")
        text = div.find_all("p")
        tag = None
        if h.strong.string.strip() == "Question":
            tag = soup.new_tag("question")
            tag["speaker_name"] = speaker.strip()
            tag["speaker_seat"] = seat.strip()
            tag["speaker_party"] = party.strip()
            tag["lodged"] = lodged.strip()
        elif h.strong.string.strip() == "Answer":
            tag = soup.new_tag("answer")
            tag["speaker_name"] = responder.strip()

        if tag:
            tag.extend(text)
            parsed.append(tag)

    soup.find("raw_html").replace_with(parsed)

    return soup


def tidy_up_wrans_html(xml_path: Path, output_dir: Path):
    """
    For each subsection there is a raw_html child
    This function will convert the raw_html element to a parsed child.
    This can be rerun on already downloaded data.
    """

    with xml_path.open("r") as f:
        xml = f.read()

    soup = BeautifulSoup(xml, "html.parser")

    for item in soup.find_all("spwrans"):
        wrans_item_url = item.get("url")

        # process html
        raw_html = item.find("raw_html")
        parsed_data = process_raw_html(raw_html, wrans_item_url=wrans_item_url)
        # replace raw_html with parsed
        item.find("raw_html").decompose()
        item.append(parsed_data.find("parsed"))

    # dump the soup to a file
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / xml_path.name
    with output_file.open("w") as f:
        f.write(soup.prettify())
