"""Transform Northern Ireland Assembly sources into supplemental Popolo.

Committee roles come from a current-only feed. Ministerial history is available
only through per-person requests, so closed histories and public committee links
are reused from the preceding artifact during routine updates.
"""

from __future__ import annotations

import re
from collections import defaultdict
from contextlib import closing
from datetime import date, timedelta
from pathlib import Path
from unicodedata import combining, normalize
from urllib.parse import parse_qs, urlparse

from mysoc_validator import Popolo
from mysoc_validator.models.dates import FixedDate
from mysoc_validator.models.popolo import (
    IdentifierScheme,
    Organization,
)
from mysoc_validator.models.popolo import (
    Membership as PopoloMembership,
)
from mysoc_validator.models.popolo import (
    Post as PopoloPost,
)

from ...config import REPO_ROOT
from ...helpers.iterables import unique
from ...helpers.link_cache import cached_organization_links
from ...helpers.organization_dates import set_organization_dates_from_memberships
from ...helpers.person_resolution import resolve_person_id
from ...helpers.progress import report
from ...helpers.reconciliation import reconcile_snapshot_memberships
from ...helpers.validation import write_and_cross_validate
from ...models.popolo_extensions import (
    CommitteeOrganizationExtra,
    MinisterialMembershipExtra,
)
from .client import (
    MEMBER_ROLE_HISTORY_URL,
    MINISTERIAL_ROLE_TYPE,
    NorthernIrelandAssemblyClient,
)
from .models import (
    AssemblyPerson,
    Committee,
    CommitteeMembershipKey,
    MemberRole,
)
from .parsing import (
    MEMBER_ROLES_URL,
    normalized_committee_name,
)

DEFAULT_PEOPLE_PATH = REPO_ROOT / "members" / "people.json"
DEFAULT_OUTPUT_PATH = REPO_ROOT / "members" / "posts" / "ni-assembly-committees.json"
COMMITTEE_ROLE_TYPE = "Committee Role (incl Assembly Commission)"
GOVERNMENT_MEMBERSHIP_PREFIX = "niassembly.gov.uk/Affiliation/"
COMMITTEE_MEMBERSHIP_PREFIX = "niassembly.gov.uk/Committee/"
EXECUTIVE_ORGANIZATION_ID = "northern-ireland-executive"


def is_committee_snapshot(membership: PopoloMembership) -> bool:
    """Return whether a membership belongs to the current-committee snapshot."""
    return membership.id.startswith(COMMITTEE_MEMBERSHIP_PREFIX)


def cached_committee_links(output_path: Path) -> dict[str, str] | None:
    """Read NI public committee links from a previous Popolo output."""
    return cached_organization_links(
        output_path,
        link_prefix="https://www.niassembly.gov.uk/assembly-business/committees/",
        key=lambda organization: normalized_committee_name(organization.name),
    )


def cached_government_memberships(
    output_path: Path,
) -> list[PopoloMembership] | None:
    """Read previously generated NI ministerial memberships."""
    if not output_path.exists():
        return None
    previous = Popolo.from_path(output_path, cross_validate=False)
    cached = [
        membership
        for membership in previous.memberships
        if membership.id.startswith(GOVERNMENT_MEMBERSHIP_PREFIX)
    ]
    if cached and all(membership.post_id is not None for membership in cached):
        return cached
    return None


def person_id_for_ni_role(
    record: MemberRole,
    people: Popolo,
    api_people: dict[int, AssemblyPerson],
) -> str:
    """Resolve an NI role holder by identifier or their name at the role date."""
    api_person = api_people.get(record.person_id)
    names: list[str] = []
    if api_person is not None:
        names = unique(
            (
                api_person.name,
                "".join(
                    character
                    for character in normalize("NFKD", api_person.name)
                    if not combining(character)
                ),
            )
        )
    return resolve_person_id(
        people,
        context=f"NI Assembly person {record.person_id}",
        source_identifier=record.person_id,
        identifier_scheme=IdentifierScheme.NI_ASSEMBLY,
        names=names,
        chamber_id="northern-ireland-assembly",
        on_date=(date.fromisoformat(record.start_date) if record.start_date else None),
        include_historical_names=True,
    )


def cached_ni_person_id(membership: PopoloMembership) -> int | None:
    """Extract the official person ID from a cached history source URL."""
    values = parse_qs(urlparse(membership.source or "").query).get("personId", [])
    if len(values) != 1 or not values[0].isdigit():
        return None
    return int(values[0])


def government_post_id(record: MemberRole) -> str:
    """Return a stable post ID from the department and official title."""
    title = record.affiliation_title or record.role
    slug = "-".join(re.findall(r"[a-z0-9]+", title.casefold()))
    return f"niassembly.gov.uk/Department/{record.committee_id}/Post/{slug}"


def government_memberships(
    roles: list[MemberRole],
    people: Popolo,
    api_people: dict[int, AssemblyPerson],
) -> list[PopoloMembership]:
    """Convert NI ministerial role histories to supplemental Popolo memberships."""
    memberships: list[PopoloMembership] = []
    for record in roles:
        if record.start_date is None:
            raise ValueError(
                f"NI ministerial affiliation {record.affiliation_id} has no start date"
            )
        person_id = person_id_for_ni_role(record, people, api_people)
        membership = PopoloMembership(
            id=f"{GOVERNMENT_MEMBERSHIP_PREFIX}{record.affiliation_id}",
            source=MEMBER_ROLE_HISTORY_URL.format(person_id=record.person_id),
            person_id=person_id,
            post_id=government_post_id(record),
            role=record.affiliation_title or record.role,
            start_date=date.fromisoformat(record.start_date),
            end_date=date.fromisoformat(record.end_date)
            if record.end_date
            else FixedDate.FUTURE,
            extra=MinisterialMembershipExtra(
                tags=[record.role_type],
                department_id=record.committee_id,
                department=record.organization_name,
            ),
        )
        memberships.append(membership)
    return memberships


def normalize_ministerial_boundaries(
    memberships: list[PopoloMembership],
) -> list[PopoloMembership]:
    """Resolve same-day handovers for Popolo inclusive end dates."""
    normalized = [membership.model_copy() for membership in memberships]
    by_person_and_post: defaultdict[tuple[str, str], list[PopoloMembership]] = (
        defaultdict(list)
    )
    for membership in normalized:
        by_person_and_post[(membership.person_id, membership.post_id or "")].append(
            membership
        )

    # The Assembly timestamps consecutive affiliations at the same midnight.
    # Popolo dates are inclusive, so close the earlier record the day before.
    for tenures in by_person_and_post.values():
        tenures.sort(key=lambda item: (item.start_date, item.id))
        for earlier, later in zip(tenures, tenures[1:]):
            if earlier.end_date == later.start_date:
                earlier.end_date = later.start_date - timedelta(days=1)
    return normalized


def committees_to_popolo(
    committees: list[Committee],
    member_roles: list[MemberRole],
    people: Popolo,
    ministerial_memberships: list[PopoloMembership] | None = None,
) -> Popolo:
    """
    Build supplemental Popolo from current committees and current MLA roles.
    """
    committees_by_id = {committee.id: committee for committee in committees}
    if not committees_by_id:
        raise ValueError("The NI Assembly API returned no current committees")
    if len(committees_by_id) != len(committees):
        raise ValueError("The NI Assembly API returned duplicate committee IDs")

    organizations = [
        Organization(
            id=f"ni-assembly-committee-{committee.id}",
            name=committee.name,
            classification="committee",
            extra=CommitteeOrganizationExtra(tags=[committee.committee_type]),
            links=[committee.external_url] if committee.external_url else [],
        )
        for committee in committees
    ]
    memberships: list[PopoloMembership] = []
    seen_memberships: set[CommitteeMembershipKey] = set()
    for record in member_roles:
        if (
            record.role_type != COMMITTEE_ROLE_TYPE
            or record.committee_id not in committees_by_id
        ):
            continue
        membership_key = CommitteeMembershipKey(
            committee_id=record.committee_id,
            person_id=record.person_id,
        )
        if membership_key in seen_memberships:
            raise ValueError(
                "Multiple current roles for NI Assembly person "
                f"{record.person_id} on committee {record.committee_id}"
            )
        seen_memberships.add(membership_key)
        person_id = resolve_person_id(
            people,
            context=f"NI Assembly person {record.person_id}",
            source_identifier=record.person_id,
            identifier_scheme=IdentifierScheme.NI_ASSEMBLY,
        )
        memberships.append(
            PopoloMembership(
                id=(
                    f"{COMMITTEE_MEMBERSHIP_PREFIX}{record.committee_id}/Member/"
                    f"{record.person_id}"
                ),
                source=MEMBER_ROLES_URL,
                person_id=person_id,
                organization_id=f"ni-assembly-committee-{record.committee_id}",
                role=record.role,
                start_date=FixedDate.PAST,
                end_date=FixedDate.FUTURE,
            )
        )

    # Historical ministerial affiliations point to posts derived from their
    # official department and title under a single Executive organization.
    government_posts: dict[str, PopoloPost] = {}
    if ministerial_memberships:
        organizations.append(
            Organization(
                id=EXECUTIVE_ORGANIZATION_ID,
                name="Northern Ireland Executive",
                classification="other",
                links=[],
            )
        )
    for membership in normalize_ministerial_boundaries(ministerial_memberships or []):
        if membership.post_id is None or membership.role is None:
            raise ValueError(f"Incomplete NI Executive membership {membership.id}")
        post_id = membership.post_id
        role = membership.role
        post = PopoloPost(
            id=post_id,
            organization_id=EXECUTIVE_ORGANIZATION_ID,
            label=role,
            role=role,
        )
        existing = government_posts.get(post_id)
        if existing is not None and existing != post:
            raise ValueError(f"Conflicting NI Executive post {post_id}")
        government_posts[post_id] = post
        memberships.append(membership)
    data = {
        "organizations": sorted(organizations, key=lambda item: item.id),
        "posts": sorted(government_posts.values(), key=lambda item: item.id),
        "memberships": sorted(memberships, key=lambda item: (item.person_id, item.id)),
    }
    return Popolo.model_validate(data, context={"skip_cross_checks": True})


def scrape_ni_assembly_committees(
    output_path: Path = DEFAULT_OUTPUT_PATH,
    people_path: Path = DEFAULT_PEOPLE_PATH,
    full_refresh: bool = False,
) -> Path:
    """
    Fetch committee and ministerial role data and write supplemental Popolo JSON.
    """
    report("Loading Northern Ireland Assembly data")
    people = Popolo.from_path(people_path)
    previous = (
        Popolo.from_path(output_path, cross_validate=False)
        if output_path.exists()
        else None
    )
    cached_links = None if full_refresh else cached_committee_links(output_path)
    cached_ministerial = (
        None if full_refresh else cached_government_memberships(output_path)
    )
    with closing(NorthernIrelandAssemblyClient()) as client:
        assembly_data = client.all_data(cached_links)
        api_people = {person.person_id: person for person in client.all_people()}
        if len(api_people) == 0:
            raise ValueError("The NI Assembly API returned no current or former MLAs")

        current_minister_ids = {
            role.person_id
            for role in assembly_data.roles
            if role.role_type == MINISTERIAL_ROLE_TYPE
        }
        if cached_ministerial is None:
            refresh_ids = set(api_people)
            retained_memberships: list[PopoloMembership] = []
        else:
            open_minister_ids = {
                person_id
                for membership in cached_ministerial
                if membership.end_date == date.max
                and (person_id := cached_ni_person_id(membership)) is not None
            }
            refresh_ids = current_minister_ids | open_minister_ids
            retained_memberships = [
                membership
                for membership in cached_ministerial
                if cached_ni_person_id(membership) not in refresh_ids
            ]

        history = client.government_role_history(refresh_ids)
    retained_memberships.extend(government_memberships(history, people, api_people))
    current = committees_to_popolo(
        assembly_data.committees, assembly_data.roles, people, retained_memberships
    )
    reconciled = reconcile_snapshot_memberships(
        previous,
        current,
        date.today(),
        is_committee_snapshot,
    )
    reconciled = set_organization_dates_from_memberships(reconciled)
    write_and_cross_validate(reconciled, output_path, people_path)
    report(f"Wrote Northern Ireland Assembly data to {output_path}")
    return output_path


if __name__ == "__main__":
    scrape_ni_assembly_committees()
