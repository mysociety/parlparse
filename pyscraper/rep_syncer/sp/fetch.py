"""
Fetch data from the Scottish Parliament API and build the flat
SPMembership intermediary file.

Steps:
  1. Download members, parse names into a PersonName lookup.
  2. Build location lookup: for a given (person_id, date) return which
     constituency or region they held.
  3. Build party ID to name lookup.
  4. Use party assignments as the membership basis; expand with lookups.
  5. Save to intermediary JSON file.
"""

from __future__ import annotations

import sys
from collections import defaultdict
from datetime import date, timedelta
from itertools import groupby
from typing import Literal, NamedTuple, Optional

from mysoc_validator.models.consts import MembershipReason

DATE_TOLERANCE = timedelta(days=14)


class LocationResult(NamedTuple):
    location_type: Literal["constituency", "region"]
    name: str
    cycle_start: date
    cycle_end: Optional[date]  # None if the election cycle is still open


from .api_models import (
    Constituency,
    ConstituencyList,
    MemberElectionConstituencyStatus,
    MemberElectionConstituencyStatusList,
    MemberElectionRegionStatus,
    MemberElectionRegionStatusList,
    MemberList,
    MemberPartyList,
    PartyList,
    Region,
    RegionList,
    SPMembership,
    SPMembershipList,
)


class PersonLocationData(NamedTuple):
    constituency_statuses: list[MemberElectionConstituencyStatus]
    region_statuses: list[MemberElectionRegionStatus]


def group_location_data(
    constituency_statuses: list[MemberElectionConstituencyStatus],
    region_statuses: list[MemberElectionRegionStatus],
) -> dict[int, PersonLocationData]:
    grouped: dict[int, PersonLocationData] = defaultdict(
        lambda: PersonLocationData([], [])
    )
    for cs in constituency_statuses:
        grouped[cs.person_id].constituency_statuses.append(cs)
    for rs in region_statuses:
        grouped[rs.person_id].region_statuses.append(rs)
    return dict(grouped)


def get_location_on_date(
    person_id: int,
    target_date: date,
    location_data: dict[int, PersonLocationData],
    constituencies: dict[int, Constituency],
    regions: dict[int, Region],
) -> Optional[LocationResult]:
    """
    Return a LocationResult(location_type, name) for the person on target_date,
    or None if no matching record exists.
    """
    if person_id not in location_data:
        return None

    loc = location_data[person_id]

    const_matches = [
        c
        for c in loc.constituency_statuses
        if c.valid_from_date <= target_date
        and (c.valid_until_date is None or c.valid_until_date >= target_date)
    ]
    if const_matches:
        best = max(const_matches, key=lambda c: c.valid_from_date)
        return LocationResult(
            "constituency",
            constituencies[best.constituency_id].name,
            best.valid_from_date,
            best.valid_until_date,
        )

    region_matches = [
        r
        for r in loc.region_statuses
        if r.valid_from_date <= target_date
        and (r.valid_until_date is None or r.valid_until_date >= target_date)
    ]
    if region_matches:
        best = max(region_matches, key=lambda r: r.valid_from_date)
        return LocationResult(
            "region",
            regions[best.region_id].name,
            best.valid_from_date,
            best.valid_until_date,
        )

    return None


def dates_close(a: date, b: date, tolerance: int = DATE_TOLERANCE.days) -> bool:
    return abs((a - b).days) <= tolerance


def compute_membership_reasons(
    memberships: list[SPMembership],
) -> list[SPMembership]:
    """
    Annotate each SPMembership with start_reason and end_reason.

    Rules (per person + seat group, sorted by start_date):
      start_reason:
        - start_date ≈ cycle_start → ELECTION (constituency) or REGIONAL_ELECTION (region)
        - Previous membership had a different party → CHANGED_PARTY
        - Otherwise → BLANK

      end_reason:
        - end_date ≈ cycle_end → DISSOLUTION
        - Next membership exists with a different party → CHANGED_PARTY
        - Last membership for this person+seat, ended early → RESIGNED
        - Otherwise → BLANK
    """
    key = lambda m: (m.scottish_parl_person_id, m.constituency_or_region_name)
    sorted_memberships = sorted(memberships, key=key)

    result: list[SPMembership] = []

    # iterate through all memberships for a person/seat
    for _, group_iter in groupby(sorted_memberships, key=key):
        group = sorted(group_iter, key=lambda m: m.start_date)
        last = len(group) - 1

        for pos, m in enumerate(group):
            # start reason is election
            if dates_close(m.start_date, m.cycle_start, tolerance=2):
                start_reason = MembershipReason.ELECTION
            # is a previous party different - this will be a party change
            elif pos > 0 and group[pos - 1].party != m.party:
                start_reason = MembershipReason.CHANGED_PARTY
            else:
                start_reason = MembershipReason.BLANK

            end_reason = MembershipReason.BLANK
            if (
                m.end_date
                and m.cycle_end
                and dates_close(m.end_date, m.cycle_end, tolerance=2)
            ):
                end_reason = MembershipReason.DISSOLUTION
            elif pos < last and group[pos + 1].party != m.party:
                end_reason = MembershipReason.CHANGED_PARTY
            elif pos == last and m.end_date is not None:
                # Last membership for this person+seat with a set end date — resigned early
                end_reason = MembershipReason.RESIGNED
            else:
                end_reason = MembershipReason.BLANK

            m.start_reason = start_reason
            m.end_reason = end_reason
            result.append(m)

    return result


def fetch_sp_memberships(*, verbose: bool = True) -> SPMembershipList:
    """
    Download all required data from the Scottish Parliament API and return
    a flat SPMembershipList combining party assignments with name and
    location information.
    """

    def log(msg: str) -> None:
        if verbose:
            print(msg, file=sys.stderr)

    log("Fetching members…")
    names = MemberList.fetch().name_lookup()
    log("Fetching parties…")
    parties = PartyList.fetch().name_lookup()

    log("Fetching party assignments…")
    member_party_list = MemberPartyList.fetch()

    log("Fetching constituency election statuses…")
    const_status_list = MemberElectionConstituencyStatusList.fetch()

    log("Fetching region election statuses…")
    region_status_list = MemberElectionRegionStatusList.fetch()

    log("Fetching constituencies…")
    constituency_list = ConstituencyList.fetch()
    constituencies = constituency_list.by_id()

    log("Fetching regions…")
    region_list = RegionList.fetch()
    regions = region_list.by_id()

    location_data = group_location_data(const_status_list.root, region_status_list.root)

    memberships: list[SPMembership] = []
    skipped = 0

    for mp in member_party_list:
        if mp.person_id not in names:
            skipped += 1
            continue

        party_name = parties.get(mp.party_id, f"Unknown party {mp.party_id}")
        name = names[mp.person_id]

        location = get_location_on_date(
            mp.person_id, mp.valid_from_date, location_data, constituencies, regions
        )
        if location is None:
            skipped += 1
            continue

        memberships.append(
            SPMembership(
                membership_id=mp.id,
                scottish_parl_person_id=mp.person_id,
                first_name=name.first_name,
                last_name=name.last_name,
                party=party_name,
                start_date=mp.valid_from_date,
                end_date=mp.valid_until_date,
                constituency_or_region=location.location_type,
                constituency_or_region_name=location.name,
                cycle_start=location.cycle_start,
                cycle_end=location.cycle_end,
            )
        )

    # add start and end reasons based on dates and party changes
    memberships = compute_membership_reasons(memberships)

    log(
        f"Built {len(memberships)} SP membership records "
        f"({skipped} skipped — no name or location data)."
    )
    return SPMembershipList(root=memberships)
