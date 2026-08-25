"""
Derive organisation founding and dissolution dates from membership dates.
"""

from __future__ import annotations

from mysoc_validator import Popolo
from mysoc_validator.models.dates import FixedDate
from mysoc_validator.models.popolo import Membership


def set_organization_dates_from_memberships(popolo: Popolo) -> Popolo:
    """
    Set each organisation's founding_date and dissolution_date from its memberships.

    founding_date becomes the earliest start_date across the organisation's
    memberships, and dissolution_date the latest end_date. An organisation with
    no memberships is left untouched.

    Where every membership's start date is the FixedDate sentinel - meaning the
    start is unknown - founding_date is cleared to None rather than set to the
    sentinel date, overriding any previously set value. The same applies to
    dissolution_date when every membership is still open.
    """
    for organization in popolo.organizations:
        memberships = popolo.memberships.get_matching_values(
            "organization_id", organization.id
        )
        if not memberships:
            continue

        memberships = [x for x in memberships if isinstance(x, Membership)]

        earliest_start = min(membership.start_date for membership in memberships)
        organization.founding_date = (
            None if earliest_start == FixedDate.PAST else earliest_start
        )

        latest_end = max(membership.end_date for membership in memberships)
        organization.dissolution_date = (
            None if latest_end == FixedDate.FUTURE else latest_end
        )

    return popolo
