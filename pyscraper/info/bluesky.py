import datetime
from pathlib import Path
from typing import Optional

from atproto import Client
from mysoc_validator import Popolo
from mysoc_validator.models.consts import Chamber
from mysoc_validator.models.info import InfoCollection, PersonInfo

from pyscraper.settings import settings


class SocialInfo(PersonInfo):
    facebook_page: Optional[str] = None
    twitter_username: Optional[str] = None
    bluesky_handle: Optional[str] = None


SocialInfoCollection = InfoCollection[SocialInfo]


def get_bluesky_list() -> list[dict[str, str]]:
    client = Client()
    # medium blue
    client.login(settings.bluesky_username, settings.bluesky_app_password)

    # We are currently depending on a politicshome list
    # https://bsky.app/profile/politicshome.bsky.social/lists/3laetww5nlb23

    list_owner = "politicshome.bsky.social"
    list_id = "3laetww5nlb23"

    owner_did = client.resolve_handle(list_owner)["did"]

    # 3. Construct the at:// URI for the list
    #    Format: at://<did>/app.bsky.graph.list/<listId>
    list_uri = f"at://{owner_did}/app.bsky.graph.list/{list_id}"

    # 4. Fetch the list items (the actual membership of the list)
    cursor = None
    response_items = []
    while True:
        response = client.app.bsky.graph.get_list({"list": list_uri, "cursor": cursor})
        response_items.extend(response.items)
        cursor = response.cursor
        if not cursor:
            break

    return [
        {"handle": x.subject.handle, "name": x.subject.display_name}
        for x in response_items
    ]


def add_person_ids(items: list[dict[str, str]]):
    popolo = Popolo.from_path(Path("members", "people.json"))

    prefixes = ["Dame ", "Dr ", "Dr. ", "Sir "]
    postfixes = [" OBE", " MBE", " KC", " AS /"]

    manual = {
        "commonsspeaker.parliament.uk": "uk.org.publicwhip/person/10295",
        "sianberry.bsky.social": "uk.org.publicwhip/person/25752",
        "alisonstaylormp.bsky.social": "uk.org.publicwhip/person/26563",
    }

    for item in items:
        if item["handle"] in manual:
            item["person_id"] = manual[item["handle"]]
            continue
        name = item["name"]
        if not name:
            name = item["handle"].split(".")[0]
            if name.endswith("mp"):
                name = name[:-2]
        if " MP" in name:
            name = name.split(" MP")[0].strip()
        for prefix in prefixes:
            if name.startswith(prefix):
                name = name[len(prefix) :]
        for postfix in postfixes:
            if name.endswith(postfix):
                name = name[: -len(postfix)]
        person = popolo.persons.from_name(
            name, chamber_id=Chamber.COMMONS, date=datetime.date.today()
        )
        if not person and "-" in name:
            name = name.split("-")[0].strip()
            person = popolo.persons.from_name(
                name, chamber_id=Chamber.COMMONS, date=datetime.date.today()
            )

        if person:
            item["person_id"] = person.id
        else:
            raise ValueError(f"Could not find person for {name}")

    lookup_dict: dict[str, str] = {item["person_id"]: item["handle"] for item in items}
    return lookup_dict


def update_xml(lookup_dict: dict[str, str]):
    social_media_links = SocialInfoCollection.from_xml_path(
        Path("members", "social-media-commons.xml")
    )

    # we need to do three things, update entries that already exist, remove entries that are no longer valid, and add new entries

    for social in social_media_links:
        if social.person_id in lookup_dict:
            social.bluesky_handle = lookup_dict[social.person_id]
        else:
            if social.bluesky_handle:
                social.bluesky_handle = None

    existing = [x.person_id for x in social_media_links]
    for person_id in lookup_dict:
        if person_id not in existing:
            social_media_links.append(
                SocialInfo(person_id=person_id, bluesky_handle=lookup_dict[person_id])
            )

    social_media_links.to_xml_path(Path("members", "social-media-commons.xml"))


def update_bluesky():
    items = get_bluesky_list()
    lookup_dict = add_person_ids(items)
    update_xml(lookup_dict)


if __name__ == "__main__":
    update_bluesky()
