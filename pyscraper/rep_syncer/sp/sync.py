"""
Compare the flat SPMembership data against people.json and
update it — adding identifiers, closing memberships, or creating new records.

Only memberships starting on or after SP_ELECTION_2021 are considered.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from mysoc_validator import Popolo
from mysoc_validator.models.consts import IdentifierScheme, MembershipReason
from mysoc_validator.models.dates import FixedDate
from mysoc_validator.models.popolo import (
    Area,
    BasicPersonName,
    Membership,
    Person,
    PersonIdentifier,
    Post,
    SimpleIdentifier,
)

from ..common import (
    dates_close,
    find_post,
    is_open_ended,
    membership_overlaps,
    memberships_for_person_and_post,
)
from .api_models import SPMembership, SPMembershipList

SP_ELECTION_2021 = date(2021, 5, 1)

# We have some small disagreements on when memberships start that we don't *need*
# to correct.
DATE_TOLERANCE = timedelta(days=5)

SP_MEMBERSHIP_SCHEME = "sp_memberparty_id"

SP_PARTY_MAP: dict[str, str] = {
    "Scottish National Party": "scottish-national-party",
    "Scottish Conservative and Unionist Party": "conservative",
    "Scottish Labour Party": "labour",
    "Scottish Labour": "labour",
    "Scottish Liberal Democrats": "liberal-democrat",
    "Scottish Green Party": "green",
    "Independent": "independent",
    "No Party Affiliation": "independent",
    "Alba Party": "alba",
    "Reform UK": "reform",
    "Scottish Socialist Party": "ssp",
    "Conservative": "conservative",
    "Labour": "labour",
    "Liberal Democrat": "liberal-democrat",
    "Green": "green",
    "Alba": "alba",
    "SSP": "ssp",
}

SP_ORG_ID = "scottish-parliament"


def resolve_party(party_name: str, log: list[str]) -> Optional[str]:
    """
    Map an SP API party name to the people.json organisation ID, or None if unknown.
    """
    org_id = SP_PARTY_MAP.get(party_name.strip())
    if org_id is None:
        log.append(f"WARNING: Unknown SP party name {party_name!r} — skipping.")
    return org_id


def ensure_post(
    popolo: Popolo, area_name: str, start_date: date, log: list[str]
) -> Post:
    """
    Return the existing post for area_name, creating it if absent.

    Post IDs follow the uk.org.publicwhip/cons/N scheme
    """
    post = find_post(popolo, area_name, SP_ORG_ID, on_date=start_date)
    if post is not None:
        return post

    existing_ids = []
    for p in popolo.posts:
        if p.id.startswith("uk.org.publicwhip/cons/"):
            suffix = p.id.split("/")[-1]
            try:
                existing_ids.append(int(suffix))
            except ValueError:
                pass
    next_id = max(existing_ids, default=10000) + 1
    new_post = Post(
        id=f"uk.org.publicwhip/cons/{next_id}",
        organization_id=SP_ORG_ID,
        area=Area(name=area_name),
        role="MSP",
        label=f"MSP for {area_name}",
        start_date=start_date,
    )

    popolo.posts.append(new_post)
    log.append(f"CREATED post: {new_post.id} — MSP for {area_name}")
    return new_post


def find_person_by_scotparl_id(popolo: Popolo, scotparl_id: int) -> Optional[Person]:
    """Look up a person by their Scottish Parliament numeric ID, or return None."""
    try:
        return popolo.persons.from_identifier(
            str(scotparl_id), scheme=IdentifierScheme.SCOTPARL
        )
    except ValueError:
        return None


def create_person(popolo: Popolo, sp: SPMembership, log: list[str]) -> Person:
    """
    Add a new Person to popolo for an MSP not yet present in people.json.

    """
    person_id = f"uk.org.publicwhip/person/{popolo.persons.get_unassigned_id()}"
    person = Person(
        id=person_id,
        names=[
            BasicPersonName(
                given_name=sp.first_name,
                family_name=sp.last_name,
                note="Main",
                start_date=FixedDate.PAST,
                end_date=FixedDate.FUTURE,
            )
        ],
    )
    person.identifiers.append(
        PersonIdentifier(
            scheme=IdentifierScheme.SCOTPARL,
            identifier=str(sp.scottish_parl_person_id),
        )
    )
    popolo.persons.append(person)
    log.append(
        f"CREATED person: {person_id} — {sp.first_name} {sp.last_name} "
        f"(scotparl_id={sp.scottish_parl_person_id})"
    )
    return person


def has_sp_identifier(m: Membership, membership_id: int) -> bool:
    """
    True if the membership already carries the given sp_memberparty_id identifier.
    """
    if not m.identifiers:
        return False
    return any(
        i.scheme == SP_MEMBERSHIP_SCHEME and i.identifier == str(membership_id)
        for i in m.identifiers
    )


def add_sp_identifier(m: Membership, membership_id: int) -> None:
    """
    Append an sp_memberparty_id identifier to an existing membership.
     If the identifier is already present, do nothing."""
    new_id = SimpleIdentifier(
        scheme=SP_MEMBERSHIP_SCHEME, identifier=str(membership_id)
    )
    if m.identifiers is None:
        m.identifiers = []
    m.identifiers.append(new_id)


def create_membership(
    popolo: Popolo,
    person: Person,
    post: Post,
    party_org_id: str,
    sp: SPMembership,
    log: list[str],
) -> None:
    """
    Append a new Membership to popolo for an SP party assignment with no
    existing counterpart in people.json.
    """

    new_m = Membership(
        id=Membership.BLANK_ID,
        person_id=person.id,
        post_id=post.id,
        on_behalf_of_id=party_org_id,
        start_date=sp.start_date,
        end_date=sp.end_date or FixedDate.FUTURE,
        start_reason=sp.start_reason,
        end_reason=sp.end_reason if sp.end_date else MembershipReason.BLANK,
        identifiers=[
            SimpleIdentifier(
                scheme=SP_MEMBERSHIP_SCHEME, identifier=str(sp.membership_id)
            )
        ],
    )
    popolo.memberships.append(new_m)
    log.append(
        f"CREATED membership: {new_m.id} — {person.id} at {post.area.name} "
        f"({party_org_id}) {sp.start_date}→{sp.end_date or 'open'}"
    )


def ensure_posts_exist(
    popolo: Popolo, memberships: SPMembershipList, log: list[str]
) -> None:
    """
    Pre-step: walk the 2021+ memberships and create any SP post that does not
    yet exist in people.json.  Each unique area name is processed once.
    """
    seen: set[str] = set()
    for sp in memberships:
        if sp.start_date < SP_ELECTION_2021:
            continue
        area = sp.constituency_or_region_name
        if area not in seen:
            seen.add(area)
            ensure_post(popolo, area, sp.start_date, log)


def sync_sp_memberships(sp_memberships: SPMembershipList, popolo: Popolo) -> list[str]:
    """
    Reconcile SP API party assignments against Scottish Parliament memberships
    in people.json, for all records starting on or after SP_ELECTION_2021.

    For each SP membership:

    1. Resolves the party name to a people.json organisation ID via SP_PARTY_MAP.
       Unknown parties are logged and skipped.

    2. Locates the post by constituency/region name

    3. Finds or creates the person using their scotparl_id identifier.  If the
       person is absent from people.json a new Person record is created.

    4. Finds all existing people.json memberships for that person + post, then
       filters to those whose date range overlaps with the SP membership.

    Five possible results:

    Zero overlaps
        The SP assignment has no counterpart: create a new Membership (e.g. a
        newly elected MSP, or an MSP who changed seat).

    Exactly one overlap — already has identifier
        Already synced in a previous run; skip silently.

    Exactly one overlap — both open-ended, start dates close
        Existing membership matches: stamp the sp_memberparty_id identifier.

    Exactly one overlap — people.json open-ended, API has an end date, start dates close
        The parliament has ended or the MSP has resigned since the last sync:
        close the membership by setting end_date and stamp the identifier.

    Exactly one overlap — both have end dates, both start and end dates close
        Fully bounded membership that matches: stamp the identifier.

    Exactly one overlap — dates don't reconcile
        Start or end dates differ beyond DATE_TOLERANCE (e.g. people.json
        records a single term but the API splits it at a party-change boundary):
        log a MISMATCH for manual review.

    Multiple overlaps
        More than one existing membership covers the SP assignment's period outside
        of tolerance size (party whip changes are usually triggering this): log a
        MULTIPLE OVERLAPS for manual review.

    """
    log: list[str] = []

    ensure_posts_exist(popolo, sp_memberships, log)

    for sp in sp_memberships:
        if sp.start_date < SP_ELECTION_2021:
            continue

        party_org_id = resolve_party(sp.party, log)
        if party_org_id is None:
            continue

        post = find_post(
            popolo, sp.constituency_or_region_name, SP_ORG_ID, on_date=sp.start_date
        )
        if post is None:
            log.append(
                f"ERROR: Post for {sp.constituency_or_region_name!r} not found "
                f"(membership_id={sp.membership_id}). Skipping."
            )
            continue

        person = find_person_by_scotparl_id(popolo, sp.scottish_parl_person_id)
        if person is None:
            person = create_person(popolo, sp, log)

        existing = memberships_for_person_and_post(popolo, person.id, post.id)
        overlapping = [m for m in existing if membership_overlaps(sp, m)]

        # When multiple memberships overlap (e.g. a whip-loss creates a
        # preceding membership that touches the API start date at its boundary),
        # narrow to those whose start date is within DATE_TOLERANCE. If exactly
        # one survives, treat it as the single true match.
        if len(overlapping) > 1:
            by_start = [
                m
                for m in overlapping
                if dates_close(
                    sp.start_date,
                    date.fromisoformat(str(m.start_date)),
                    DATE_TOLERANCE.days,
                )
            ]
            if len(by_start) == 1:
                overlapping = by_start
            elif len(by_start) > 1:
                # Secondary tiebreaker: prefer the membership whose party matches
                by_party = [m for m in by_start if m.on_behalf_of_id == party_org_id]
                if len(by_party) == 1:
                    overlapping = by_party

        if len(overlapping) == 0:
            create_membership(popolo, person, post, party_org_id, sp, log)

        elif len(overlapping) == 1:
            m = overlapping[0]
            ex_start = date.fromisoformat(str(m.start_date))
            start_match = dates_close(sp.start_date, ex_start, DATE_TOLERANCE.days)

            if has_sp_identifier(m, sp.membership_id):
                continue

            if sp.end_date is None and is_open_ended(m):
                if start_match:
                    add_sp_identifier(m, sp.membership_id)
                    log.append(
                        f"UPDATED identifier on {m.id} (sp_memberparty_id={sp.membership_id})"
                    )
                else:
                    log.append(
                        f"MISMATCH (open-ended): {m.id} ({person.id}) start {ex_start} vs "
                        f"API start {sp.start_date} — manual review needed "
                        f"(membership_id={sp.membership_id})"
                    )

            elif sp.end_date is not None and is_open_ended(m):
                if start_match:
                    m.end_date = sp.end_date
                    m.end_reason = sp.end_reason
                    add_sp_identifier(m, sp.membership_id)
                    log.append(
                        f"CLOSED membership {m.id} → end_date={sp.end_date} "
                        f"(sp_memberparty_id={sp.membership_id})"
                    )
                else:
                    log.append(
                        f"MISMATCH (closing): {m.id} ({person.id}) start {ex_start} vs "
                        f"API start {sp.start_date}, end {sp.end_date} — "
                        f"manual review needed (membership_id={sp.membership_id})"
                    )

            else:
                ex_end = date.fromisoformat(str(m.end_date))
                end_match = sp.end_date is not None and dates_close(
                    sp.end_date, ex_end, DATE_TOLERANCE.days
                )
                if start_match and end_match:
                    add_sp_identifier(m, sp.membership_id)
                    log.append(
                        f"UPDATED identifier on {m.id} (sp_memberparty_id={sp.membership_id})"
                    )
                else:
                    log.append(
                        f"MISMATCH: {m.id} ({person.id}) [{ex_start}→{ex_end}] vs "
                        f"API [{sp.start_date}→{sp.end_date}] — "
                        f"manual review needed (membership_id={sp.membership_id})"
                    )

        else:
            overlap_details = ", ".join(
                f"{m.id} [[cyan]{m.start_date}[/cyan]→[cyan]{m.end_date}[/cyan]] [yellow]({m.on_behalf_of_id})[/yellow]"
                for m in overlapping
            )
            log.append(
                f"MULTIPLE OVERLAPS ({len(overlapping)}) for person {person.id} "
                f"at post {post.id} — API: "
                f"[[cyan]{sp.start_date}[/cyan]→[cyan]{sp.end_date or 'open'}[/cyan]] [yellow]({party_org_id})[/yellow]. "
                f"Existing: {overlap_details}. "
                f"Manual review needed — likely a small date discrepancy."
            )

    return log
