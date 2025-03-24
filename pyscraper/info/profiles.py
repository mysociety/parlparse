from pathlib import Path
from typing import Optional

import httpx
from mysoc_validator import InfoCollection, PersonInfo, Popolo
from mysoc_validator.models.consts import IdentifierScheme
from pydantic import AnyHttpUrl


class OfficialProfile(PersonInfo):
    profile_url_uk_parl: Optional[AnyHttpUrl] = None
    profile_url_senedd_en: Optional[AnyHttpUrl] = None
    profile_url_senedd_cy: Optional[AnyHttpUrl] = None
    profile_url_scot_parl: Optional[AnyHttpUrl] = None
    profile_url_ni_assembly: Optional[AnyHttpUrl] = None


ProfileCollection = InfoCollection[OfficialProfile]

senedd_format_en = "https://senedd.wales/people/{their_id}"
senedd_format_cy = "https://senedd.cymru/pobl/{their_id}"
parl_format = "https://members.parliament.uk/member/{their_id}/career"
mla_format = (
    "https://aims.niassembly.gov.uk/mlas/details.aspx?per={their_id}&sel=1&ind=0&prv=0"
)


def get_official_profile_urls():
    popolo = Popolo.from_path(Path("members", "people.json"))

    SCOT_WEBSITE_API = "https://data.parliament.scot/api/websites"

    data = httpx.get(SCOT_WEBSITE_API).json()
    scot_person_to_url = {
        d["PersonID"]: AnyHttpUrl(d["WebURL"])
        for d in data
        if d["WebSiteTypeID"] == 1 and d["WebURL"]
    }

    collection = ProfileCollection()

    for p in popolo.persons:
        profile = OfficialProfile(person_id=p.id)
        has_added = False
        for ident in p.identifiers:
            if ident.scheme == IdentifierScheme.SENEDD:
                profile.profile_url_senedd_en = AnyHttpUrl(
                    senedd_format_en.format(their_id=ident.identifier)
                )
                profile.profile_url_senedd_cy = AnyHttpUrl(
                    senedd_format_cy.format(their_id=ident.identifier)
                )
                has_added = True
            if ident.scheme == IdentifierScheme.MNIS:
                profile.profile_url_uk_parl = AnyHttpUrl(
                    parl_format.format(their_id=ident.identifier)
                )
                has_added = True
            if ident.scheme == IdentifierScheme.SCOTPARL:
                if url := scot_person_to_url.get(int(ident.identifier)):
                    profile.profile_url_scot_parl = url
                    has_added = True
            if ident.scheme == IdentifierScheme.NI_ASSEMBLY:
                profile.profile_url_ni_assembly = AnyHttpUrl(
                    mla_format.format(their_id=ident.identifier)
                )
                has_added = True
        if has_added:
            collection.append(profile)

    collection.to_xml_path(Path("members", "official-profiles.xml"))


if __name__ == "__main__":
    get_official_profile_urls()
