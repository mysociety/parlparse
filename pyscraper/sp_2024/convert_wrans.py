"""
Convert the structured data from Scottish Parliament to
the XML format used by TheyWorkForYou

Link to TWFY IDs for members.
"""

import datetime
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from lxml import etree

from .resolvenames import get_unique_person_id, is_member_vote


@dataclass
class IDFactory:
    iso_date: str
    ref: str = ""
    base_id: str = "uk.org.publicwhip/spwa/"
    q_num: int = -1

    def _current_id(self) -> str:
        return f"{self.base_id}{self.iso_date}.{self.latest_major}.{self.latest_minor}"

    def set_ref(self, ref):
        self.ref = ref

    def get_next_major_id(self) -> str:
        return f"{self.base_id}{self.iso_date}.mh"

    def get_next_minor_id(self) -> str:
        self.q_num = 0
        return f"{self.base_id}{self.iso_date}.{self.ref}.h"

    def get_next_q_id(self) -> str:
        return f"{self.base_id}{self.iso_date}.{self.ref}.q{self.q_num}"

    def get_next_r_id(self) -> str:
        id = f"{self.base_id}{self.iso_date}.{self.ref}.r{self.q_num}"
        self.q_num += 1
        return id


def convert_wrans_xml_to_twfy(file_path: Path, output_dir: Path, verbose: bool = False):
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

    iso_date = source.get("date")

    # get the date in format Thursday 9 June 2005
    date_str = datetime.date.fromisoformat(iso_date).strftime("%A %d %B %Y")

    dest_path = output_dir / f"spwa{iso_date}.xml"
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    id_factory = IDFactory(iso_date=iso_date)

    # there is only questions for today
    major_heading = etree.Element("major-heading")
    major_heading.set("id", id_factory.get_next_major_id())
    major_heading.set("nospeaker", "True")
    # major_heading.set("url", item.get("url"))
    major_heading.text = f"Written Questions for {date_str}"
    root.append(major_heading)

    # iterate through the questions
    for item in source.iter("spwrans"):
        id_factory.set_ref(item.get("id"))

        # each question is a minor heading using the id as the title because
        # we don't have anything else to use
        minor_heading = etree.Element("minor-heading")
        minor_heading.set("id", id_factory.get_next_minor_id())
        minor_heading.text = f"Question {item.get('id')}"
        root.append(minor_heading)

        missing_speakers = []
        for subitem in item.find("parsed"):
            if subitem.tag == "question":
                speaker_name = subitem.get("speaker_name")
                person_id = get_unique_person_id(speaker_name, iso_date)
                if (
                    person_id is None
                    and speaker_name not in missing_speakers
                    and verbose
                ):
                    print(f"Could not find person id for {speaker_name}")
                    missing_speakers.append(speaker_name)
                speech = etree.Element("ques")
                speech.set("id", id_factory.get_next_q_id())
                speech.set("url", item.get("url") or "")
                speech.set("speakername", speaker_name)
                speech.set("person_id", person_id or "unknown")
                for child in subitem:
                    speech.append(child)
                root.append(speech)

            elif subitem.tag == "answer":
                speaker_name = subitem.get("speaker_name")
                person_id = get_unique_person_id(speaker_name, iso_date)
                if (
                    person_id is None
                    and speaker_name not in missing_speakers
                    and verbose
                ):
                    print(f"Could not find person id for {speaker_name}")
                    missing_speakers.append(speaker_name)
                speech = etree.Element("reply")
                speech.set("id", id_factory.get_next_r_id())
                speech.set("url", item.get("url") or "")
                speech.set("speakername", speaker_name)
                speech.set("person_id", person_id or "unknown")
                for child in subitem:
                    speech.append(child)
                root.append(speech)

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
        convert_wrans_xml_to_twfy(xml, output_dir, verbose=verbose)
