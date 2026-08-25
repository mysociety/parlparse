"""Transform Westminster MNIS and Committees API history into Popolo.

MNIS IDs join both sources to parlparse people. Parliamentary post records are
already dated; committee overlaps become non-overlapping tenures enriched with
cached committee metadata.
"""

from __future__ import annotations

import re
import warnings
from collections import defaultdict
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
from ...helpers.organization_dates import set_organization_dates_from_memberships
from ...helpers.progress import report
from ...helpers.validation import write_and_cross_validate
from ...models.popolo_extensions import CommitteeOrganizationExtra
from .client import WestminsterClient
from .models import (
    CachedCommitteeRecord,
    CommitteeMembership,
    CommitteeMetadata,
    MembershipKey,
    Post,
)
from .parsing import (
    HISTORY_START,
    POST_TYPES,
    committee_organization_name,
    normalized_committee_roles,
    overlaps_history,
    slugify,
)

DEFAULT_PEOPLE_PATH = REPO_ROOT / "members" / "people.json"
DEFAULT_OUTPUT_PATH = (
    REPO_ROOT / "members" / "posts" / "westminster-parliament-posts.json"
)


def cached_committee_metadata(
    output_path: Path,
) -> dict[int, CommitteeMetadata]:
    """Read committee metadata from a previous Westminster Popolo output."""
    if not output_path.exists():
        return {}

    previous = Popolo.from_path(output_path, cross_validate=False)
    committee_link = re.compile(
        r"^https://committees\.parliament\.uk/committee/(\d+)/$"
    )
    records: list[CachedCommitteeRecord] = []
    ids_by_organization: dict[str, int] = {}
    for organization in previous.organizations:
        match = next(
            (
                committee_link.fullmatch(link)
                for link in organization.links
                if committee_link.fullmatch(link)
            ),
            None,
        )
        if match is None:
            continue
        committee_id = int(match.group(1))
        external_url = match.group(0)
        ids_by_organization[organization.id] = committee_id
        records.append(
            CachedCommitteeRecord(
                organization=organization,
                committee_id=committee_id,
                external_url=external_url,
            )
        )

    metadata: dict[int, CommitteeMetadata] = {}
    for record in records:
        tags = tuple(record.organization.get_extra("tags") or ())
        metadata[record.committee_id] = CommitteeMetadata(
            id=record.committee_id,
            name=record.organization.name,
            parent_id=(
                ids_by_organization.get(record.organization.parent_id)
                if record.organization.parent_id is not None
                else None
            ),
            categories=tags,
            description=record.organization.description,
            external_url=record.external_url,
        )
    return metadata


def roles_to_popolo(
    posts: list[Post],
    committee_memberships: list[CommitteeMembership],
    people: Popolo,
    history_start: date = HISTORY_START,
    committee_metadata: dict[int, CommitteeMetadata] | None = None,
) -> Popolo:
    """
    Convert Westminster post and committee histories to supplemental Popolo.
    """
    source_mnis_ids = sorted(
        {
            *(post.member_id for post in posts),
            *(membership.member_id for membership in committee_memberships),
        }
    )
    people_by_mnis: dict[int, str] = {}
    unresolved_mnis_ids: list[int] = []
    for member_id in source_mnis_ids:
        try:
            person = people.persons.from_identifier(
                str(member_id), scheme=IdentifierScheme.MNIS
            )
        except ValueError:
            unresolved_mnis_ids.append(member_id)
        else:
            people_by_mnis[member_id] = person.id
    if unresolved_mnis_ids:
        warnings.warn(
            "Skipping unresolved MNIS people: "
            + ", ".join(str(member_id) for member_id in unresolved_mnis_ids),
            stacklevel=2,
        )
    organizations: dict[str, Organization] = {}
    memberships: list[PopoloMembership] = []
    counters: defaultdict[MembershipKey, int] = defaultdict(int)
    seen_posts: set[Post] = set()
    # Membership responses retain historic committee summaries; cached/current
    # detail records add remit text, hierarchy and category tags.
    metadata_by_id = {
        record.committee_id: record.metadata
        or CommitteeMetadata(
            id=record.committee_id,
            name=committee_organization_name(record.committee_name),
            external_url=(
                f"https://committees.parliament.uk/committee/{record.committee_id}/"
            ),
        )
        for record in committee_memberships
    }
    if committee_metadata:
        metadata_by_id.update(committee_metadata)

    def add_committee_organization(
        committee_id: int, adding: set[int] | None = None
    ) -> str:
        metadata = metadata_by_id[committee_id]
        name = committee_organization_name(metadata.name)
        organization_id = slugify(name)
        if organization_id in organizations:
            return organization_id

        adding = adding or set()
        if committee_id in adding:
            raise ValueError(f"Committee {committee_id} has a circular parent")
        adding.add(committee_id)

        parent_id: str | None = None
        if metadata.parent_id in metadata_by_id:
            parent_id = add_committee_organization(metadata.parent_id, adding)

        organizations[organization_id] = Organization(
            id=organization_id,
            name=name,
            classification="committee",
            parent_id=parent_id,
            description=metadata.description,
            links=[metadata.external_url] if metadata.external_url else [],
            extra=(
                CommitteeOrganizationExtra(tags=list(metadata.categories))
                if metadata.categories
                else None
            ),
        )
        return organization_id

    # Repeated source post IDs can describe separate dated tenures, so suffixes
    # preserve each appointment as a unique Popolo membership.
    for post in sorted(
        posts,
        key=lambda item: (
            item.member_id,
            item.post_type,
            item.post_id,
            item.start_date,
            item.end_date or date.max,
        ),
    ):
        if post in seen_posts or post.member_id not in people_by_mnis:
            continue
        seen_posts.add(post)
        counter_key = MembershipKey(post.member_id, post.post_type, post.post_id)
        count = counters[counter_key]
        counters[counter_key] += 1
        membership_id = (
            f"uk.parliament.data/Member/{post.member_id}/{post.post_type}/"
            f"{post.post_id}"
        )
        if count:
            membership_id += f"/{count}"
        membership = PopoloMembership(
            id=membership_id,
            source=f"datadotparl/{POST_TYPES[post.post_type]}",
            role=post.name,
            person_id=people_by_mnis[post.member_id],
            organization_id="house-of-commons",
            start_date=post.start_date,
            end_date=post.end_date or FixedDate.FUTURE,
        )
        memberships.append(membership)

    for record in sorted(
        committee_memberships,
        key=lambda item: (item.member_id, item.committee_id),
    ):
        if record.member_id not in people_by_mnis:
            continue
        organization_id = add_committee_organization(record.committee_id)
        counter_key = MembershipKey(record.member_id, "Committee", record.committee_id)
        for role in normalized_committee_roles(record.roles):
            if not overlaps_history(role.end_date, history_start):
                continue
            count = counters[counter_key]
            counters[counter_key] += 1
            membership_id = (
                f"uk.parliament.data/Member/{record.member_id}/Committee/"
                f"{record.committee_id}"
            )
            if count:
                membership_id += f"/{count}"
            membership = PopoloMembership(
                id=membership_id,
                source="datadotparl/committee",
                person_id=people_by_mnis[record.member_id],
                organization_id=organization_id,
                start_date=role.start_date,
                role=role.name,
                end_date=role.end_date or FixedDate.FUTURE,
            )
            memberships.append(membership)

    data = {
        "organizations": sorted(organizations.values(), key=lambda item: item.id),
        "memberships": sorted(memberships, key=lambda item: (item.person_id, item.id)),
    }
    return Popolo.model_validate(data, context={"skip_cross_checks": True})


def scrape_westminster_roles(
    output_path: Path = DEFAULT_OUTPUT_PATH,
    people_path: Path = DEFAULT_PEOPLE_PATH,
    history_start: date = HISTORY_START,
    request_delay: float = 3.0,
    batch_size: int = 50,
    full_refresh: bool = False,
) -> Path:
    """
    Fetch Westminster role histories and write supplemental Popolo JSON.
    """
    report("Loading Westminster role histories")
    people = Popolo.from_path(people_path)
    with closing(WestminsterClient(request_delay=request_delay)) as client:
        posts = client.posts(history_start)
        committees = client.committee_memberships(
            [
                int(identifier.identifier)
                for person in people.persons
                for identifier in person.identifiers
                if identifier.scheme == IdentifierScheme.MNIS
            ],
            history_start,
            batch_size,
        )
        cached_metadata = {} if full_refresh else cached_committee_metadata(output_path)
        committee_metadata = client.committee_details(
            committees,
            cached_metadata=cached_metadata,
            full_refresh=full_refresh,
        )
    popolo = roles_to_popolo(
        posts,
        committees,
        people,
        history_start,
        committee_metadata,
    )
    popolo = set_organization_dates_from_memberships(popolo)
    write_and_cross_validate(popolo, output_path, people_path)
    report(f"Wrote Westminster role data to {output_path}")
    return output_path


if __name__ == "__main__":
    scrape_westminster_roles()
