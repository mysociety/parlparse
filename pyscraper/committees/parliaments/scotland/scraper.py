"""
Fetch Scottish Parliament committees and government posts as Popolo data.
"""

from __future__ import annotations

import re
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
from ...helpers.iterables import unique
from ...helpers.link_cache import cached_organization_links
from ...helpers.organization_dates import set_organization_dates_from_memberships
from ...helpers.person_resolution import resolve_person_id
from ...helpers.progress import report
from ...helpers.reconciliation import reconcile_snapshot_memberships
from ...helpers.validation import write_and_cross_validate
from .client import (
    MEMBER_GOVERNMENT_ROLES_URL,
    PERSON_COMMITTEE_ROLES_URL,
    ScottishParliamentClient,
)
from .models import (
    CommitteeData,
    CommitteeMembershipKey,
    ScottishPerson,
)
from .parsing import clean_description

DEFAULT_PEOPLE_PATH = REPO_ROOT / "members" / "people.json"
DEFAULT_OUTPUT_PATH = (
    REPO_ROOT / "members" / "posts" / "scottish-parliament-committees.json"
)
STAFF_ROLE_IDS = frozenset({4, 7})
SCOTTISH_NAME_ALIASES = {
    # Source names that differ from the dated names retained in people.json.
    "Natalie Don-Innes": "Natalie Don",
    "Ash Regan": "Ash Denham",
    "Hannah Mary Goodlad": "Hannah Goodlad",
}
COMMITTEE_MEMBERSHIP_PREFIX = "parliament.scot/Committee/"


def is_committee_snapshot(membership: PopoloMembership) -> bool:
    """Return whether a membership belongs to the current-committee snapshot."""
    return membership.id.startswith(COMMITTEE_MEMBERSHIP_PREFIX)


def cached_committee_links(output_path: Path) -> dict[str, str] | None:
    """Read Scottish public committee links from a previous Popolo output."""
    return cached_organization_links(
        output_path,
        link_prefix=(
            "https://www.parliament.scot/chamber-and-committees/"
            "committees/current-and-previous-committees/"
        ),
        key=lambda organization: organization.name,
    )


def person_for_scottish_id(
    person_id: int,
    people: Popolo,
    api_people: dict[int, ScottishPerson],
    on_date: date,
) -> str:
    """Resolve a Scottish API person ID, falling back to its dated name."""
    api_person = api_people.get(person_id)
    names: list[str] = []
    if api_person is not None:
        surname, separator, given_names = api_person.parliamentary_name.partition(",")
        name = (
            f"{given_names.strip()} {surname.strip()}"
            if separator
            else api_person.parliamentary_name.strip()
        )
        name = re.sub(
            r"^(?:Mr|Ms|Mrs|Miss|Dr|Sir|Dame|Lord|Lady)\s+",
            "",
            name,
            flags=re.IGNORECASE,
        )
        names = unique(item for item in (name, SCOTTISH_NAME_ALIASES.get(name)) if item)
    return resolve_person_id(
        people,
        context=f"Scottish Parliament person {person_id}",
        source_identifier=person_id,
        identifier_scheme=IdentifierScheme.SCOTPARL,
        names=(name for name in names if name),
        chamber_id="scottish-parliament",
        on_date=on_date,
    )


def committees_to_popolo(
    data: CommitteeData,
    people: Popolo,
    membership_date: date,
) -> Popolo:
    """
    Build supplemental Popolo for committees active on a given date.
    """
    api_people = {person.person_id: person for person in data.members}
    if len(api_people) != len(data.members):
        raise ValueError("The Scottish Parliament API returned duplicate person IDs")

    committees_by_id = {committee.id: committee for committee in data.committees}
    if len(committees_by_id) != len(data.committees):
        raise ValueError("The Scottish Parliament API returned duplicate committee IDs")

    active_committees = {
        committee_id: committee
        for committee_id, committee in committees_by_id.items()
        if committee.active_on(membership_date)
    }
    if not active_committees:
        raise ValueError(
            f"No Scottish Parliament committees active on {membership_date}"
        )

    # Role definitions and person assignments are separate feeds. Staff roles
    # share the assignment feed but are not parliamentary memberships.
    roles_by_id = {role.id: role for role in data.roles}
    if len(roles_by_id) != len(data.roles):
        raise ValueError("The Scottish Parliament API returned duplicate role IDs")

    organizations = [
        Organization(
            id=f"scottish-parliament-committee-{committee.id}",
            name=committee.name,
            classification="committee",
            description=(
                clean_description(committee.description)
                if committee.description.strip()
                else None
            ),
            links=unique(
                link
                for link in (
                    data.committee_links.get(committee.name),
                    committee.blog_website,
                )
                if link
            ),
        )
        for committee in active_committees.values()
    ]
    memberships: list[PopoloMembership] = []
    seen_memberships: set[CommitteeMembershipKey] = set()
    for record in data.person_roles:
        if record.committee_id not in active_committees or not record.active_on(
            membership_date
        ):
            continue
        if record.committee_role_id not in roles_by_id:
            raise ValueError(f"Unknown committee role ID {record.committee_role_id}")
        if record.committee_role_id in STAFF_ROLE_IDS:
            continue

        membership_key = CommitteeMembershipKey(
            committee_id=record.committee_id,
            person_id=record.person_id,
        )
        if membership_key in seen_memberships:
            raise ValueError(
                "Multiple current roles for Scottish Parliament person "
                f"{record.person_id} on committee {record.committee_id}"
            )
        seen_memberships.add(membership_key)

        person_id = person_for_scottish_id(
            record.person_id, people, api_people, membership_date
        )

        organization_id = f"scottish-parliament-committee-{record.committee_id}"
        memberships.append(
            PopoloMembership(
                id=(
                    f"parliament.scot/Committee/{record.committee_id}/Member/"
                    f"{record.person_id}"
                ),
                source=PERSON_COMMITTEE_ROLES_URL,
                person_id=person_id,
                organization_id=organization_id,
                role=roles_by_id[record.committee_role_id].name,
                start_date=FixedDate.PAST,
                end_date=FixedDate.FUTURE,
            )
        )

    # Government role names and dated appointments are separate datasets;
    # unlike committees, these records already contain authoritative history.
    government_roles_by_id = {role.id: role for role in data.government_roles}
    if len(government_roles_by_id) != len(data.government_roles):
        raise ValueError(
            "The Scottish Parliament API returned duplicate government role IDs"
        )
    for government_record in data.member_government_roles:
        role = government_roles_by_id.get(government_record.government_role_id)
        if role is None:
            raise ValueError(
                f"Unknown government role ID {government_record.government_role_id}"
            )
        person_id = person_for_scottish_id(
            government_record.person_id,
            people,
            api_people,
            government_record.valid_from.date(),
        )
        membership = PopoloMembership(
            id=f"scot.parliament.data/membergovernmentroles/{government_record.id}",
            source=MEMBER_GOVERNMENT_ROLES_URL,
            person_id=person_id,
            organization_id="scottish-parliament",
            role=role.name,
            start_date=government_record.valid_from.date(),
            end_date=government_record.valid_until.date()
            if government_record.valid_until
            else FixedDate.FUTURE,
        )
        memberships.append(membership)

    popolo_data = {
        "organizations": sorted(organizations, key=lambda item: item.id),
        "memberships": sorted(memberships, key=lambda item: (item.person_id, item.id)),
    }
    return Popolo.model_validate(
        popolo_data,
        context={"skip_cross_checks": True},
    )


def scrape_scottish_parliament_committees(
    output_path: Path = DEFAULT_OUTPUT_PATH,
    people_path: Path = DEFAULT_PEOPLE_PATH,
    membership_date: date | None = None,
    full_refresh: bool = False,
) -> Path:
    """
    Fetch committee and government role data and write supplemental Popolo JSON.
    """
    report("Loading Scottish Parliament data")
    people = Popolo.from_path(people_path)
    previous = (
        Popolo.from_path(output_path, cross_validate=False)
        if output_path.exists()
        else None
    )
    cached_links = None if full_refresh else cached_committee_links(output_path)
    with closing(ScottishParliamentClient()) as client:
        data = client.get_data(cached_links)
    on_date = membership_date or date.today()
    current = committees_to_popolo(data, people, on_date)
    reconciled = reconcile_snapshot_memberships(
        previous,
        current,
        on_date,
        is_committee_snapshot,
    )
    reconciled = set_organization_dates_from_memberships(reconciled)
    write_and_cross_validate(reconciled, output_path, people_path)
    report(f"Wrote Scottish Parliament data to {output_path}")
    return output_path


if __name__ == "__main__":
    scrape_scottish_parliament_committees()
