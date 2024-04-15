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


def process_raw_html(raw_html: Tag, agenda_item_url: str) -> BeautifulSoup:
    """
    Given the debate html, convert it to a structured xml format
    This isn't yet matching TWFY schema or using the right IDs.
    The goal is to make a structured file that's a bit easier to work with.
    """

    # Deal with timestamps that are not inside anything first
    raw_html = str(raw_html)
    raw_html = re.sub(
        "(?m)^\s*(.*?)\s*<br/>\s*<br/>", r"<timestamp>\1</timestamp>", raw_html
    )
    soup = BeautifulSoup(raw_html, "html.parser")

    # convert a structure where there's a strong tag with an a inside to a speech tag

    for strong in soup.find_all("strong"):
        a = strong.find("a")

        if a and a.get("href"):
            speaker = soup.new_tag("speech")
            speaker["speaker_name"] = strong.text.strip()
            speaker["speaker_href"] = a["href"]
            speaker["speaker_scot_id"] = a["name"]
            strong.replace_with(speaker)
        elif a and a.get("name", "") == "0":
            # This is a speaker without a member link - outside speakers, religious ministers, etc
            speaker = soup.new_tag("speech")
            speaker["speaker_name"] = strong.text.strip()
            strong.replace_with(speaker)

    # if there is a div that just contains a speech
    # promote the speech tag to the higher level and delete the div
    for div in soup.find_all("div"):
        reduced_contents = [x for x in div.contents if str(x).strip() != ""]
        if len(reduced_contents) == 1 and div.find("speech"):
            speaker = div.find("speech")
            div.replace_with(speaker)

    # if there is a p that just contains a speech, promote the speech tag to the higher level
    # move the id of the p to a speech_link_id attribute on the speech tag
    for p in soup.find_all("p"):
        reduced_contents = [x for x in p.contents if str(x).strip() != ""]
        if len(reduced_contents) == 1 and p.find("speech"):
            speaker = p.find("speech")
            speaker["speech_url"] = agenda_item_url + "#" + p["id"]
            p.replace_with(speaker)

    # This is for finding topical question headings
    for p in soup.find_all("p", class_="lead"):
        heading = soup.new_tag("heading")
        heading.string = p.string
        heading["url"] = agenda_item_url + "#" + p["id"]
        p.replace_with(heading)

    # This is a speaker with some meta-speech e.g. "rose-"
    # or multiple speakers and the like, e.g. "Members: No"
    for p in soup.find_all("p", class_="or-contribution-box"):
        bold = p.find(class_="or-bill-section-bold")
        italic = p.find(class_="or-italic")
        if bold and bold.text.strip():
            speech = soup.new_tag("speech")
            speech["speaker_name"] = bold.text.strip()
            bold.decompose()
            text = p.text.strip()
            new_p = soup.new_tag("p")
            if italic:
                new_p["class"] = "italic"
            new_p.string = text
            speech.append(new_p)
            p.replace_with(speech)

    # for all remaining span or-italic, we just want to make these italics
    for span in soup.find_all("span", class_="or-italic"):
        del span["class"]
        span.name = "i"

    # sequential tags from an acceptable element should be grouped together under the speech
    # to create the speech object
    for speaker in soup.find_all("speech"):
        next_sibling = speaker.find_next_sibling()
        while next_sibling and next_sibling.name in acceptable_elements:
            # if the class is 'or-contribution-box' remove that class
            if next_sibling.get("class") == ["or-contribution-box"]:
                del next_sibling["class"]
            speaker.append(next_sibling)
            next_sibling = speaker.find_next_sibling()

    # there are currently timestamps inside speeches
    # we want to move these after their parent
    # move these in reverse so that consequentive timestamps
    # end up in the right order
    for timestamp in soup.find_all("timestamp")[::-1]:
        timestamp.parent.insert_after(timestamp)

    # now, in each speech - we want to iterate through and check for a p tag that's just 'For' or 'Against'
    # if so the next sibling will be a list of speakers seperated by <br/>
    # we want to create a msplist tag, with a direction of 'For' or 'Against'
    # and then a list of speakers as 'mspname' tags
    for speaker in soup.find_all("speech"):
        for_tag = speaker.find("p", string="For")
        against_tag = speaker.find("p", string="Against")
        abstain_tag = speaker.find("p", string="Abstentions")
        for vote_tag in [for_tag, against_tag, abstain_tag]:
            if vote_tag:
                vote_str = vote_tag.text.lower()
                vote_div = soup.new_tag("msplist")
                vote_div["vote"] = vote_str
                # get all the speakers in the next sibling
                members = vote_tag.find_next_sibling("p").stripped_strings

                for m in members:
                    mspname = soup.new_tag("mspname")
                    mspname["vote"] = vote_str
                    mspname.string = m
                    vote_div.append(mspname)

                vote_tag.find_next_sibling("p").decompose()
                speaker.append(vote_div)
                vote_tag.decompose()

        # now we want to wrap any sequential msplists tags in a division tag
        vote_tags = speaker.find_all("msplist")
        if len(vote_tags) > 1:
            division_tag = soup.new_tag("division")
            vote_tags[0].insert_before(division_tag)
            for vote_tag in vote_tags:
                division_tag.append(vote_tag)

        # for all division tags, we want to:
        # - set a sequential divnum for the day
        # - create a divisioncount object that counts the for, against abstensions
        # and spoiled ballots (always 0 for sp)

        for div_num, division in enumerate(speaker.find_all("division")):
            div_counts = {"for": 0, "against": 0, "abstentions": 0, "spoiledvotes": 0}
            division["divnum"] = div_num
            divisioncount = soup.new_tag("divisioncount")
            for vote in division.find_all("mspname"):
                div_counts[vote["vote"]] += 1

            for k, v in div_counts.items():
                divisioncount[k] = str(v)

            division.insert(0, divisioncount)

        # all divisions are currently part of the original speech,
        # we want to split the speech into
        # two speeches before and after (copy across properties)
        # and put the division object between them
        for division in speaker.find_all("division"):
            parent = division.parent
            if parent.name != "speech":
                raise ValueError("Division not in speech")

            division_pos = parent.index(division)
            before = parent.contents[:division_pos]
            after = parent.contents[division_pos + 1 :]

            # move division up to be after original speech
            parent.insert_after(division)

            # reduce the original speech to just the content before the division
            parent.clear()
            parent.extend(before)

            # create a new speech element with the content after the division
            if len(after) > 0:
                new_speech = soup.new_tag("speech")
                # get all attrbs from original speech
                for k, v in speaker.attrs.items():
                    new_speech[k] = v
                new_speech.extend(after)
                division.insert_after(new_speech)

    soup.find("raw_html").name = "parsed"

    return soup


def tidy_up_html(xml_path: Path):
    """
    For each subsection there is a raw_html child
    This function will convert the raw_html element to a parsed child.
    This can be rerun on already downloaded data.
    """

    with xml_path.open("r") as f:
        xml = f.read()

    soup = BeautifulSoup(xml, "html.parser")

    for item in soup.find_all("agenda_item"):
        agenda_item_url = item.get("url")

        # delete any 'parsed' child of the subsection element
        for child in item.find_all("parsed"):
            child.decompose()

        # process html
        raw_html = item.find("raw_html")
        parsed_data = process_raw_html(raw_html, agenda_item_url=agenda_item_url)
        item.append(parsed_data.find("parsed"))

    # dump the soup to a file
    with xml_path.open("w") as f:
        f.write(soup.prettify())
