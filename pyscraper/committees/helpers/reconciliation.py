"""Reconcile current-only membership feeds with the preceding Popolo output."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta
from typing import NamedTuple, TypeVar

from mysoc_validator import Popolo
from mysoc_validator.models.popolo import Membership, Organization, Post

MembershipSelector = Callable[[Membership], bool]
Record = TypeVar("Record", Organization, Post)


class MembershipIdentity(NamedTuple):
    """Source-independent fields that identify one continuous tenure."""

    person_id: str
    organization_id: str
    post_id: str


def membership_identity(membership: Membership) -> MembershipIdentity:
    """Return the fallback identity used when a source membership ID changes."""
    return MembershipIdentity(
        person_id=membership.person_id,
        organization_id=membership.organization_id or "",
        post_id=membership.post_id or "",
    )


def has_known_start(membership: Membership) -> bool:
    """Return whether the validator value represents a real source start date."""
    return membership.start_date != date.min


def is_closed(membership: Membership) -> bool:
    """Return whether the validator value represents a closed tenure."""
    return membership.end_date != date.max


def unique_membership_id(base_id: str, used_ids: set[str]) -> str:
    """Allocate a tenure ID without replacing an earlier, closed tenure."""
    if base_id not in used_ids:
        return base_id
    suffix = 2
    while f"{base_id}/{suffix}" in used_ids:
        suffix += 1
    return f"{base_id}/{suffix}"


def detached_membership_copy(membership: Membership) -> Membership:
    """Copy a membership without retaining its source collection as parent."""
    copied = membership.model_copy()
    copied.parent = None
    return copied


def merge_records(
    previous: list[Record],
    current: list[Record],
) -> list[Record]:
    """Merge model records by ID, preferring the current version of each record."""
    records = {record.id: record.model_copy() for record in previous}
    records.update({record.id: record.model_copy() for record in current})
    return sorted(records.values(), key=lambda record: record.id)


def reconcile_snapshot_memberships(
    previous: Popolo | None,
    current: Popolo,
    observed_on: date,
    should_reconcile: MembershipSelector,
) -> Popolo:
    """Add inferred tenure dates to memberships from current-only sources.

    ``current`` is today's complete scraper result. Some memberships in it come
    from APIs that report only who holds a role now; ``should_reconcile`` selects
    those snapshot memberships. Other memberships have authoritative dates and
    pass through unchanged.

    ``previous`` is the artifact written on the preceding run. It supplies the
    history absent from a current-only API: an active record that remains in the
    current snapshot continues, one that disappears ends the day before this
    observation, and an already closed record remains as history. If somebody
    returns after a closed tenure, the new tenure receives a suffixed ID rather
    than reopening or overwriting the old one.

    """
    # Copy records before changing IDs or dates. The scraper.s current object may
    # still be inspected by its caller, while previous should continue to describe
    # exactly what was read from disk. Copies are detached from their original
    # IndexedMembershipList so validator assignment hooks do not revalidate inputs.
    current_memberships = [
        detached_membership_copy(membership) for membership in current.memberships
    ]
    previous_memberships = (
        [detached_membership_copy(membership) for membership in previous.memberships]
        if previous is not None
        else []
    )

    # Split snapshot records from memberships whose source already supplies
    # dates. Only the snapshot side participates in historical inference.
    current_snapshots = [
        membership for membership in current_memberships if should_reconcile(membership)
    ]
    previous_snapshots = [
        membership
        for membership in previous_memberships
        if should_reconcile(membership)
    ]

    # A current feed must contain at most one record for a person/role identity.
    # Indexing it now both validates that assumption and makes matching explicit.
    current_by_identity: dict[MembershipIdentity, Membership] = {}
    for membership in current_snapshots:
        identity = membership_identity(membership)
        if identity in current_by_identity:
            raise ValueError(f"Duplicate current snapshot membership {identity}")
        current_by_identity[identity] = membership

    # Previous closed records are immutable history. Previous active records are
    # indexed twice: source ID is the strongest match, while identity is a
    # fallback for sources that change an ID (or after a person-record merge).
    active_previous_by_identity: dict[MembershipIdentity, Membership] = {}
    active_previous_by_id: dict[str, Membership] = {}
    closed_previous: list[Membership] = []
    for membership in previous_snapshots:
        if is_closed(membership):
            closed_previous.append(membership)
            continue
        identity = membership_identity(membership)
        if identity in active_previous_by_identity:
            raise ValueError(f"Duplicate active snapshot membership {identity}")
        active_previous_by_identity[identity] = membership
        active_previous_by_id[membership.id] = membership

    # IDs belonging to history or authoritative memberships cannot be reused.
    # This set is what turns a reappearance into /2, /3, and so on.
    used_ids = {
        membership.id
        for membership in previous_memberships
        + [
            membership
            for membership in current_memberships
            if not should_reconcile(membership)
        ]
    }

    reconciled = closed_previous
    for identity, membership in current_by_identity.items():
        # Prefer source ID because it survives changes to person_id. Remove a
        # match from both indexes so it cannot be paired with a second record.
        previous_membership = active_previous_by_id.pop(membership.id, None)
        if previous_membership is not None:
            active_previous_by_identity.pop(
                membership_identity(previous_membership), None
            )
        else:
            previous_membership = active_previous_by_identity.pop(identity, None)
            if previous_membership is not None:
                active_previous_by_id.pop(previous_membership.id, None)

        if previous_membership is None:
            # This is either genuinely new or a return after a closed tenure.
            membership.id = unique_membership_id(membership.id, used_ids)
            used_ids.add(membership.id)
        else:
            # This tenure continues. Keep its established ID and retain a start
            # date only when the preceding artifact actually contained one.
            membership.id = previous_membership.id
            if has_known_start(previous_membership):
                membership.start_date = previous_membership.start_date

        reconciled.append(membership)

    # Anything left in the active indexes was present before but vanished today.
    # Close it yesterday: observed_on is the first known non-member day.
    ended_on = observed_on - timedelta(days=1)
    for membership in active_previous_by_id.values():
        membership.end_date = ended_on
        reconciled.append(membership)

    # Authoritatively dated current records bypass reconciliation completely.
    untouched = [
        membership
        for membership in current_memberships
        if not should_reconcile(membership)
    ]
    memberships = sorted(
        untouched + reconciled,
        key=lambda membership: (membership.person_id, membership.id),
    )

    # Historical memberships can refer to organizations/posts absent from
    # today's scrape. Retain those records, with current metadata winning when
    # the same ID occurs in both artifacts.
    organizations = [
        organization.model_copy() for organization in current.organizations
    ]
    posts = [post.model_copy() for post in current.posts]
    if previous is not None:
        organizations = merge_records(list(previous.organizations), organizations)
        posts = merge_records(list(previous.posts), posts)

    # Revalidation reconnects collection parents and checks record shapes.
    # Cross-collection checks remain deferred because supplemental files
    # intentionally omit the people collection they reference.
    return Popolo.model_validate(
        {
            "memberships": memberships,
            "organizations": organizations,
            "persons": [person.model_copy() for person in current.persons],
            "posts": posts,
        },
        context={"skip_cross_checks": True},
    )
