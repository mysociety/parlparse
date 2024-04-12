"""
Functions and models for interfacing with the external popolo file
"""

import datetime
import json
import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterator, Optional

from .config import get_config

# Set up logging
logger = logging.getLogger(__name__)


def strip_regex_patterns_from_string(name: str) -> str:
    """Remove titles and other patterns from a name"""

    config = get_config()
    patterns_to_strip = True

    while patterns_to_strip:
        original_name = name

        for pattern in config["name_regex_to_strip"]:
            name = re.sub(pattern, "", name)

        for title in config["office_map"].values():
            pattern = " \\({0}\\)$".format(title)
            name = re.sub(pattern, "", name)

        for title in config["office_map"].keys():
            pattern = " \\({0}\\)$".format(title)
            name = re.sub(pattern, "", name)

        if name == original_name:
            patterns_to_strip = False

    return name.strip()


def get_names_from_person(person: dict) -> Iterator[str]:
    """
    return a string name from a popolo person object
    """
    main_found = False
    for name in person.get("other_names", []):
        if name["note"] == "Main":
            main_found = True
        if "given_name" in name and "family_name" in name:
            yield name["given_name"] + " " + name["family_name"]
        if "lordname" in name:
            yield name["honorific_prefix"] + " " + name["lordname"]
    if not main_found:
        raise Exception("Unable to find main name for person {}".format(person["id"]))


class MembershipManager:
    """
    Interface with external popolo file to reconcile and fetch names
    """

    members_file = Path(__file__).parents[2] / "members" / "people.json"

    def __init__(self, members_file: Optional[Path] = None):
        """ """
        if members_file is None:
            members_file = self.__class__.members_file
        self.memberships = get_memberships(members_file)

    @classmethod
    @lru_cache(maxsize=None)
    def get_name_from_date(cls, office_name: str, date: datetime.datetime) -> str:
        # get iso date from datetime
        iso_date = date.isoformat().split("T")[0]
        # open the popolo and get all memberships for this office
        with cls.members_file.open() as file_contents:
            members_raw_data = json.load(file_contents)

        # go through posts and get the id for this office
        office_id = None
        for post in members_raw_data["posts"]:
            if post["label"] == office_name:
                office_id = post["id"]
                break

        if office_id is None:
            print("Unable to find office with name {}".format(office_name))
            return office_name

        # get the membership for this date
        correct_membership = None
        for membership in members_raw_data["memberships"]:
            if membership.get("post_id") == office_id:
                if membership["start_date"] <= iso_date:
                    if (
                        membership.get("end_date") is None
                        or membership["end_date"] >= iso_date
                    ):
                        correct_membership = membership
                        break

        if correct_membership is None:
            raise Exception(
                "Unable to find membership for office {} on date {}".format(
                    office_name, iso_date
                )
            )

        # get the name from the person
        person_id = correct_membership["person_id"]

        for person in members_raw_data["persons"]:
            if person["id"] == person_id:
                return list(get_names_from_person(person))[0]

        raise Exception("Unable to find person with id {}".format(person_id))

    def get_id_from_name(self, name: str, date_of_answer: datetime.datetime) -> str:
        """Turn a name into a speaker ID."""
        config = get_config()

        if name in list(config["office_map"].values()):
            name = self.get_name_from_date(name, date_of_answer)

        # Strip out titles and other patterns
        name = strip_regex_patterns_from_string(name)

        # If this person's name has a correction, use that instead
        if name in config["name_corrections"]:
            name = config["name_corrections"][name]

        person_id = self.memberships.get(name)

        if person_id is None:
            # in principle this is a person that changes, and could be fixed through position
            if name == "Chair, London Assembly":
                person_id = "london-assembly-chair"

        if person_id is None:
            print(
                f"Unable to find ID for {name}, return uk.org.publicwhip/person/00000."
            )
            return "uk.org.publicwhip/person/00000"

        return person_id


@lru_cache(maxsize=None)
def get_memberships(members_file: Path) -> Dict[str, str]:
    """Parse the provided file and extract data on Assembly members."""

    with members_file.open() as file_contents:
        members_raw_data = json.load(file_contents)

    logger.debug(
        "Loaded {} people from {}".format(
            len(members_raw_data["persons"]), members_file.name
        )
    )

    people_by_id = {}
    post_org_by_id = {}

    # map of person id to person object
    for person in members_raw_data["persons"]:
        people_by_id[person["id"]] = person

    # map of post id to organization id
    for post in members_raw_data["posts"]:
        post_org_by_id[post["id"]] = post["organization_id"]

    # This loops through each membership, checks to see if it's for the Assembly, if so adds it to the map

    person_ids_by_name = {}

    for membership in members_raw_data["memberships"]:
        if (
            "post_id" in membership
            and post_org_by_id[membership["post_id"]] == "london-assembly"
        ):
            for name in get_names_from_person(people_by_id[membership["person_id"]]):
                if name not in person_ids_by_name:
                    person_ids_by_name[name] = membership["person_id"]
                    logger.debug("Added ID map for for {}".format(name))
                else:
                    if person_ids_by_name[name] != membership["person_id"]:
                        raise Exception("Multiple people with name {}".format(name))

    logger.debug(
        "Added {} names with Assembly memberships".format(len(person_ids_by_name))
    )

    return person_ids_by_name
