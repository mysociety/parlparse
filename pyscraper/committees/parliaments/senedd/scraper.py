"""Transform bilingual Senedd and Welsh Government pages into Popolo.

English and Welsh sources are independently resolved to parlparse people and
must describe the same membership set. Both committee and ministerial sources
are current-only snapshots, so the preceding output provides inferred history.
"""

from __future__ import annotations

from contextlib import closing
from datetime import date
from pathlib import Path

from mysoc_validator import Popolo
from mysoc_validator.models.dates import FixedDate
from mysoc_validator.models.popolo import (
    IdentifierScheme,
    Organization,
)
from mysoc_validator.models.popolo import (
    Membership as PopoloMembership,
)

from ...config import REPO_ROOT
from ...helpers.http import HttpClient
from ...helpers.organization_dates import set_organization_dates_from_memberships
from ...helpers.person_resolution import resolve_person_id, unique_person_id_by_name
from ...helpers.progress import report, track
from ...helpers.reconciliation import reconcile_snapshot_memberships
from ...helpers.validation import write_and_cross_validate
from ...models.popolo_extensions import CommitteeOrganizationExtra
from .models import (
    BilingualCommittee,
    BilingualGovernmentMember,
    BilingualMember,
    Committee,
    CommitteeSummary,
    GovernmentMember,
    Language,
    MemberCard,
)
from .parsing import (
    government_member_name,
    is_current_committee,
    parse_committee_list,
    parse_committee_page,
    parse_government_members,
    parse_members_csv,
)

DEFAULT_PEOPLE_PATH = REPO_ROOT / "members" / "people.json"
DEFAULT_OUTPUT_PATH = REPO_ROOT / "members" / "posts" / "senedd-committees.json"
SENEDD_CHAMBER_ID = "welsh-parliament"
GOVERNMENT_PAGE_EN = "https://www.gov.wales/cabinet-ministers-and-deputy-ministers"
GOVERNMENT_PAGE_CY = "https://www.llyw.cymru/gweinidogion-y-cabinet-dirprwy-weinidogion"
SNAPSHOT_MEMBERSHIP_PREFIXES = ("senedd.wales/Committee/", "gov.wales/Minister/")
ENGLISH = Language(
    culture="en-GB",
    csv_name_column="Name",
    committee_list_url="https://business.senedd.wales/mgwebservice.asmx/GetCommittees",
    website_url="https://senedd.wales",
    committee_path="committee",
    current_categories=frozenset({"Committees", "Business Committee"}),
)
WELSH = Language(
    culture="cy-GB",
    csv_name_column="Enw",
    committee_list_url="https://busnes.senedd.cymru/mgwebservicew.asmx/GetCommittees",
    website_url="https://senedd.cymru",
    committee_path="pwyllgor",
    current_categories=frozenset({"Pwyllgorau", "Y Pwyllgor Busnes"}),
)


def fetch_committee_list(
    client: HttpClient, language: Language
) -> list[CommitteeSummary]:
    """Fetch and parse one language's ModernGov committee catalogue."""
    return parse_committee_list(
        client.get(language.committee_list_url).content,
        language.committee_list_url,
    )


def fetch_committee(
    client: HttpClient, summary: CommitteeSummary, language: Language
) -> Committee:
    """Fetch and parse one committee page and its membership CSV."""
    # The page supplies the internal ID used to construct the CSV endpoint;
    # the CSV is the authoritative current membership list.
    page_response = client.get(language.committee_url(summary.modern_gov_id))
    committee = parse_committee_page(
        summary, str(page_response.url), page_response.text, language
    )
    members_response = client.get(committee.csv_url)
    return committee._replace(
        members=parse_members_csv(committee, members_response.content, language)
    )


def fetch_all_committees(client: HttpClient) -> list[BilingualCommittee]:
    """Fetch current committees and pair their English and Welsh records."""
    english = {
        item.modern_gov_id: item
        for item in fetch_committee_list(client, ENGLISH)
        if is_current_committee(item, ENGLISH)
    }
    welsh = {
        item.modern_gov_id: item
        for item in fetch_committee_list(client, WELSH)
        if is_current_committee(item, WELSH)
    }
    if not english:
        raise ValueError(
            f"No current English Senedd committees found in {ENGLISH.committee_list_url}"
        )
    if not welsh:
        raise ValueError(
            f"No current Welsh Senedd committees found in {WELSH.committee_list_url}"
        )
    if english.keys() != welsh.keys():
        raise ValueError(
            "English and Welsh current committee lists differ; "
            f"English only: {sorted(english.keys() - welsh.keys(), key=int)}; "
            f"Welsh only: {sorted(welsh.keys() - english.keys(), key=int)}"
        )

    committees: list[BilingualCommittee] = []
    internal_ids: set[str] = set()
    for modern_gov_id in track(
        sorted(english, key=int), "Fetching bilingual Senedd committees"
    ):
        english_committee = fetch_committee(client, english[modern_gov_id], ENGLISH)
        welsh_committee = fetch_committee(client, welsh[modern_gov_id], WELSH)
        if english_committee.id != welsh_committee.id:
            raise ValueError(
                "English and Welsh pages disagree on internal committee ID: "
                f"{english_committee.page_url} and {welsh_committee.page_url}"
            )
        if english_committee.id in internal_ids:
            raise ValueError(
                f"The Senedd pages returned duplicate internal ID {english_committee.id}"
            )
        internal_ids.add(english_committee.id)
        committees.append(
            BilingualCommittee(english=english_committee, welsh=welsh_committee)
        )
    return committees


def fetch_government_members(
    client: HttpClient, page_url: str
) -> list[GovernmentMember]:
    """Fetch and parse one language's current Welsh Government team."""
    response = client.get(page_url)
    return parse_government_members(response.text, str(response.url))


def is_current_snapshot(membership: PopoloMembership) -> bool:
    """Return whether a membership comes from a current-only Senedd source."""
    return membership.id.startswith(SNAPSHOT_MEMBERSHIP_PREFIXES)


def person_id_for_member(
    member: MemberCard, people: Popolo, membership_date: date
) -> str:
    """Resolve a scraped member by Senedd ID, then their dated chamber name."""
    return resolve_person_id(
        people,
        context=f"Senedd member {member.name!r}",
        source_identifier=member.senedd_id,
        identifier_scheme=IdentifierScheme.SENEDD,
        names=(member.name,),
        chamber_id=SENEDD_CHAMBER_ID,
        on_date=membership_date,
    )


def pair_committee_members(
    committee: BilingualCommittee, people: Popolo, membership_date: date
) -> list[BilingualMember]:
    """
    Pair English and Welsh member records using their resolved TWFY IDs.

    Duplicate members or disagreement between the two language sources raise
    ``ValueError``. Results are sorted by person ID for deterministic output.
    """
    english_by_person_id = {
        person_id_for_member(member, people, membership_date): member
        for member in committee.english.members
    }
    welsh_by_person_id = {
        person_id_for_member(member, people, membership_date): member
        for member in committee.welsh.members
    }
    if len(english_by_person_id) != len(committee.english.members):
        raise ValueError(
            f"Committee {committee.english.id} contains a duplicate English member"
        )
    if len(welsh_by_person_id) != len(committee.welsh.members):
        raise ValueError(
            f"Committee {committee.welsh.id} contains a duplicate Welsh member"
        )
    if english_by_person_id.keys() != welsh_by_person_id.keys():
        raise ValueError(
            "English and Welsh member lists for committee "
            f"{committee.english.id} differ; "
            "English only: "
            f"{sorted(english_by_person_id.keys() - welsh_by_person_id.keys())}; "
            "Welsh only: "
            f"{sorted(welsh_by_person_id.keys() - english_by_person_id.keys())}"
        )
    result: list[BilingualMember] = []
    for person_id in sorted(english_by_person_id):
        english_member = english_by_person_id[person_id]
        welsh_member = welsh_by_person_id[person_id]
        if (
            english_member.senedd_id is None
            or english_member.senedd_id != welsh_member.senedd_id
        ):
            raise ValueError(f"English and Welsh Senedd IDs differ for {person_id}")
        result.append(
            BilingualMember(
                person_id=person_id,
                source_person_id=english_member.senedd_id,
                english=english_member,
                welsh=welsh_member,
            )
        )
    return result


def person_id_for_government_member(
    member: GovernmentMember, people: Popolo, membership_date: date
) -> str:
    """Resolve a minister, including office-holders who are not current MSs."""
    name = government_member_name(member.name)
    return resolve_person_id(
        people,
        context=f"Welsh Government member {member.name!r}",
        names=(name,),
        chamber_id=SENEDD_CHAMBER_ID,
        on_date=membership_date,
        fallback=unique_person_id_by_name,
    )


def pair_government_members(
    english: list[GovernmentMember],
    welsh: list[GovernmentMember],
    people: Popolo,
    membership_date: date,
) -> list[BilingualGovernmentMember]:
    """Pair bilingual current ministers by their TWFY person IDs."""

    def keyed(
        members: list[GovernmentMember],
    ) -> dict[str, GovernmentMember]:
        result: dict[str, GovernmentMember] = {}
        for member in members:
            person_id = person_id_for_government_member(member, people, membership_date)
            if person_id in result:
                raise ValueError(f"Duplicate Welsh Government role for {person_id}")
            result[person_id] = member
        return result

    english_by_id = keyed(english)
    welsh_by_id = keyed(welsh)
    if english_by_id.keys() != welsh_by_id.keys():
        raise ValueError(
            "English and Welsh Government member lists differ; "
            f"English only: {sorted(english_by_id.keys() - welsh_by_id.keys())}; "
            f"Welsh only: {sorted(welsh_by_id.keys() - english_by_id.keys())}"
        )
    return [
        BilingualGovernmentMember(
            person_id=person_id,
            english=english_by_id[person_id],
            welsh=welsh_by_id[person_id],
        )
        for person_id in sorted(english_by_id)
    ]


def committees_to_popolo(
    committees: list[BilingualCommittee],
    people: Popolo,
    membership_date: date,
    government_members: list[BilingualGovernmentMember] | None = None,
) -> Popolo:
    """
    Build supplemental Popolo organizations and memberships for the Senedd.

    Canonical committee names and roles use ``Welsh / English``. Each language
    is also stored through ``set_localised_value``. Person and organization
    cross-checks are deferred until this supplemental data is loaded alongside
    ``people.json``.
    """
    organizations: list[Organization] = []
    memberships: list[PopoloMembership] = []
    for committee in sorted(committees, key=lambda item: item.english.id):
        english = committee.english
        welsh = committee.welsh
        organization_id = f"senedd-committee-{english.id}"
        # Keep Welsh before English to match the canonical bilingual fields.
        tags = list(
            dict.fromkeys(
                category for category in (welsh.category, english.category) if category
            )
        )
        organization = Organization(
            id=organization_id,
            name=f"{welsh.name} / {english.name}",
            classification="committee",
            links=[welsh.page_url, english.page_url],
            description=(
                f"{welsh.description}\n\n{english.description}"
                if english.description and welsh.description
                else (welsh.description or english.description)
            ),
            extra=CommitteeOrganizationExtra(tags=tags) if tags else None,
        )
        organization.set_localised_value("name", "cy", welsh.name)
        organization.set_localised_value("name", "en", english.name)
        if english.description and welsh.description:
            organization.set_localised_value("description", "cy", welsh.description)
            organization.set_localised_value("description", "en", english.description)
        organizations.append(organization)

        for member in pair_committee_members(committee, people, membership_date):
            membership_id = (
                f"senedd.wales/Committee/{english.id}/Member/{member.source_person_id}"
            )
            if bool(member.english.role) != bool(member.welsh.role):
                raise ValueError(
                    "English and Welsh roles disagree for "
                    f"{member.person_id} in committee {english.id}"
                )
            role = None
            if member.english.role and member.welsh.role:
                role = f"{member.welsh.role} / {member.english.role}"
            membership = PopoloMembership(
                id=membership_id,
                source=english.csv_url,
                person_id=member.person_id,
                organization_id=organization_id,
                role=role,
                start_date=FixedDate.PAST,
                end_date=FixedDate.FUTURE,
            )
            if member.english.role and member.welsh.role:
                membership.set_localised_value("role", "cy", member.welsh.role)
                membership.set_localised_value("role", "en", member.english.role)
            memberships.append(membership)

    # Welsh Government offices come from separate public pages, but their
    # holders resolve against the same people collection as committee members.
    for government_member in government_members or []:
        membership_id = (
            "gov.wales/Minister/" + government_member.person_id.rsplit("/", 1)[-1]
        )
        membership = PopoloMembership(
            id=membership_id,
            source=GOVERNMENT_PAGE_EN,
            person_id=government_member.person_id,
            organization_id=SENEDD_CHAMBER_ID,
            role=(f"{government_member.welsh.role} / {government_member.english.role}"),
            start_date=FixedDate.PAST,
            end_date=FixedDate.FUTURE,
        )
        membership.set_localised_value("role", "cy", government_member.welsh.role)
        membership.set_localised_value("role", "en", government_member.english.role)
        memberships.append(membership)
    data = {
        "organizations": sorted(organizations, key=lambda item: item.id),
        "memberships": sorted(memberships, key=lambda item: (item.person_id, item.id)),
    }
    # Supplemental files are cross-validated after combining with people.json.
    popolo = Popolo.model_validate(data, context={"skip_cross_checks": True})
    return popolo


def scrape_senedd_committees(
    output_path: Path = DEFAULT_OUTPUT_PATH,
    people_path: Path = DEFAULT_PEOPLE_PATH,
    membership_date: date | None = None,
) -> Path:
    """
    Fetch current bilingual committee and government data as supplemental Popolo.

    ``membership_date`` defaults to today and controls which historic Senedd
    membership is used when resolving names to TWFY person IDs. The returned
    path is the file written by the scraper.
    """
    report("Loading Senedd and Welsh Government data")
    people = Popolo.from_path(people_path)
    previous = (
        Popolo.from_path(output_path, cross_validate=False)
        if output_path.exists()
        else None
    )
    with closing(HttpClient()) as client:
        committees = fetch_all_committees(client)
        english_government = fetch_government_members(client, GOVERNMENT_PAGE_EN)
        welsh_government = fetch_government_members(client, GOVERNMENT_PAGE_CY)
    on_date = membership_date or date.today()
    # A missing translation must not silently create a one-language record.
    government = pair_government_members(
        english_government, welsh_government, people, on_date
    )
    current = committees_to_popolo(committees, people, on_date, government)
    reconciled = reconcile_snapshot_memberships(
        previous,
        current,
        on_date,
        is_current_snapshot,
    )
    reconciled = set_organization_dates_from_memberships(reconciled)
    write_and_cross_validate(reconciled, output_path, people_path)
    report(f"Wrote Senedd data to {output_path}")
    return output_path


if __name__ == "__main__":
    scrape_senedd_committees()
