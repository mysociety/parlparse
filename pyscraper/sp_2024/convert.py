"""
Convert the structured data from Scottish Parliament to
the XML format used by TheyWorkForYou

Link to TWFY IDs for members and debate items.
"""

import datetime
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from lxml import etree

from .resolvenames import get_unique_person_id, is_member_vote


def slugify(text: str) -> str:
    """
    Convert a string to a url safe slug
    """
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text).replace(" ", "-")

    return text


@dataclass
class IDFactory:
    committee_slug: str
    iso_date: str
    base_id: str = "uk.org.publicwhip/spor/"
    latest_major: int = -1
    latest_minor: int = -1

    def _current_id(self) -> str:
        if self.committee_slug in ('meeting-of-the-parliament', 'plenary'):
            slug = ''
        else:
            slug = self.committee_slug + '/'
        return f"{self.base_id}{slug}{self.iso_date}.{self.latest_major}.{self.latest_minor}"

    def get_next_major_id(self) -> str:
        self.latest_major += 1
        self.latest_minor = 0
        return self._current_id()

    def get_next_minor_id(self) -> str:
        self.latest_minor += 1
        return self._current_id()


def slugify_committee(name: str) -> str:
    """
    Convert a committee name to a slug
    """
    name = slugify(name)
    # if this ends in a year (four digita number) - assume it's a date and remove the last three elements
    if name[-4:].isdigit():
        name = "-".join(name.split("-")[:-3])

    return name


def convert_xml_to_twfy(file_path: Path, output_dir: Path, verbose: bool = False):
    """
    Convert from the loose structured xml format to the
    TWFY xml format
    """
    if verbose:
        print(f"Converting {file_path}")

    # get source as an xml tree
    with file_path.open("r") as f:
        source = etree.fromstring(f.read())

    # root of the tree is a publicwhip object
    root = etree.Element("publicwhip")

    url = source.get("url")
    title = source.get("title")
    iso_date = source.get("date")
    source_id = int(float(source.get("id")[1:]))
    timestamp = ""

    # remove [Draft] from title
    title = title.replace("[Draft]", "").strip()

    # get the date in format Thursday 9 June 2005
    date_str = datetime.date.fromisoformat(iso_date).strftime("%A %d %B %Y")

    committee_slug = slugify_committee(title)

    dest_path = output_dir / committee_slug / f"{iso_date}_{source_id}.xml"
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    id_factory = IDFactory(committee_slug=committee_slug, iso_date=iso_date)

    # iterate through the agenda_items
    for item in source.iter("agenda_item"):
        # create a new major-heading from the agenda_item information
        major_heading = etree.Element("major-heading")
        major_heading.set("id", id_factory.get_next_major_id())
        major_heading.set("url", item.get("url"))
        major_heading.set("nospeaker", "True")
        major_heading.text = item.get("title")
        root.append(major_heading)

        # iterate through the agenda_item's subitems
        # if item is a speech or a division, get the new informaton and bring across
        previous_speech = None
        missing_speakers = []
        for subitem in item.find("parsed"):
            if subitem.tag == "speech":
                speaker_name = subitem.get("speaker_name")
                scot_parl_id = subitem.get("speaker_scot_id")
                person_id = get_unique_person_id(
                    speaker_name, iso_date, lookup_key=scot_parl_id
                )
                if (
                    person_id is None
                    and speaker_name not in missing_speakers
                    and verbose
                ):
                    print(f"Could not find person id for {speaker_name}")
                    missing_speakers.append(speaker_name)
                speech = etree.Element("speech")
                speech.set("id", id_factory.get_next_minor_id())
                speech.set("url", subitem.get("speech_url") or "")
                speech.set("speakername", speaker_name)
                if timestamp:
                    speech.set("time", timestamp)
                speech.set("person_id", person_id or "unknown")
                for child in subitem:
                    speech.append(child)
                root.append(speech)
                previous_speech = speech

            elif subitem.tag == "timestamp":
                if m := re.match("\s*(\d\d:\d\d)(.*)", subitem.text):
                    timestamp = m.group(1)
                    text = m.group(2)
                else:
                    text = subitem.text
                text = text.replace("\xa0", " ").strip()
                if text:
                    p = etree.Element("p")
                    p.set("class", "italic")
                    p.text = text
                    speech = etree.Element("speech")
                    speech.set("id", id_factory.get_next_minor_id())
                    speech.set("url", subitem.get("speech_url") or "")
                    if timestamp:
                        speech.set("time", timestamp)
                    speech.append(p)
                    root.append(speech)

            elif subitem.tag == "heading":
                minor_heading = etree.Element("minor-heading")
                minor_heading.set("id", id_factory.get_next_minor_id())
                minor_heading.set("url", item.get("url"))
                minor_heading.text = subitem.text
                root.append(minor_heading)

            elif subitem.tag == "division":
                # get previous sibling of the subitem to get the speech info

                if previous_speech is None:
                    raise ValueError("Division without a previous speech")

                division = etree.Element("division")
                division.set("id", id_factory.get_next_minor_id())
                division.set("url", previous_speech.get("url"))
                division.set("divdate", iso_date)
                division.set("divnumber", subitem.get("divnum"))
                division.set("nospeaker", "True")
                for child in subitem:
                    division.append(child)
                root.append(division)

    # for all mspnames elements, we need to create an ID property
    for mspname in root.iter("mspname"):
        person_name = mspname.text
        person_id = is_member_vote(person_name, iso_date)
        if person_id is None:
            print(f"Could not find person id for {person_name}")
        mspname.set("id", person_id or "unknown")

    # write the new xml to a file
    etree.indent(root, space="    ")

    with dest_path.open("wb") as f:
        f.write(etree.tostring(root, pretty_print=True))


def convert_to_twfy(
    cache_dir: Path,
    output_dir: Path,
    partial_file_name: Optional[str] = None,
    verbose: bool = False,
):
    """
    Given a cache directory, parse the raw_html elements in the xml files
    This updates the 'parsed' element under each agenda-item.
    """
    if partial_file_name:
        xmls = list(cache_dir.glob(f"{partial_file_name}*"))
    else:
        xmls = list(cache_dir.glob("*.xml"))
    for xml in xmls:
        convert_xml_to_twfy(xml, output_dir, verbose=verbose)
