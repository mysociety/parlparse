from __future__ import annotations

from mysoc_validator import Popolo

from pyscraper.committees.helpers.organization_dates import (
    set_organization_dates_from_memberships,
)


def popolo(
    organizations: list[dict[str, object]],
    memberships: list[dict[str, object]],
) -> Popolo:
    return Popolo.model_validate(
        {"organizations": organizations, "memberships": memberships},
        context={"skip_cross_checks": True},
    )


def test_sets_founding_and_dissolution_from_earliest_and_latest_membership() -> None:
    """A closed organisation date range must span all membership tenures."""
    current = popolo(
        [{"id": "current-org", "name": "Current"}],
        [
            {
                "id": "member/1",
                "person_id": "uk.org.publicwhip/person/1",
                "organization_id": "current-org",
                "start_date": "2020-01-01",
                "end_date": "2021-06-01",
            },
            {
                "id": "member/2",
                "person_id": "uk.org.publicwhip/person/2",
                "organization_id": "current-org",
                "start_date": "2019-03-01",
                "end_date": "2020-12-01",
            },
        ],
    )
    result = set_organization_dates_from_memberships(current)

    organization = result.organizations["current-org"]
    assert organization.founding_date is not None
    assert organization.dissolution_date is not None
    assert organization.founding_date.isoformat() == "2019-03-01"
    assert organization.dissolution_date.isoformat() == "2021-06-01"


def test_clears_founding_date_when_earliest_start_is_unknown() -> None:
    """One unknown membership start must make the derived founding date unknown."""
    current = popolo(
        [{"id": "current-org", "name": "Current", "founding_date": "2000-01-01"}],
        [
            {
                "id": "member/1",
                "person_id": "uk.org.publicwhip/person/1",
                "organization_id": "current-org",
                "end_date": "2021-06-01",
            },
            {
                "id": "member/2",
                "person_id": "uk.org.publicwhip/person/2",
                "organization_id": "current-org",
                "start_date": "2019-03-01",
                "end_date": "2020-12-01",
            },
        ],
    )
    result = set_organization_dates_from_memberships(current)

    organization = result.organizations["current-org"]
    assert organization.founding_date is None


def test_clears_dissolution_date_when_latest_end_is_still_open() -> None:
    """One active membership must prevent the organisation being marked dissolved."""
    current = popolo(
        [
            {
                "id": "current-org",
                "name": "Current",
                "dissolution_date": "2025-01-01",
            }
        ],
        [
            {
                "id": "member/1",
                "person_id": "uk.org.publicwhip/person/1",
                "organization_id": "current-org",
                "start_date": "2020-01-01",
            },
            {
                "id": "member/2",
                "person_id": "uk.org.publicwhip/person/2",
                "organization_id": "current-org",
                "start_date": "2019-03-01",
                "end_date": "2020-12-01",
            },
        ],
    )
    result = set_organization_dates_from_memberships(current)

    organization = result.organizations["current-org"]
    assert organization.dissolution_date is None


def test_overrides_existing_explicit_dates_with_derived_values() -> None:
    """Snapshot-derived dates must replace stale dates copied from prior output."""
    current = popolo(
        [
            {
                "id": "current-org",
                "name": "Current",
                "founding_date": "1999-01-01",
                "dissolution_date": "1999-12-31",
            }
        ],
        [
            {
                "id": "member/1",
                "person_id": "uk.org.publicwhip/person/1",
                "organization_id": "current-org",
                "start_date": "2019-03-01",
                "end_date": "2020-12-01",
            },
        ],
    )
    result = set_organization_dates_from_memberships(current)

    organization = result.organizations["current-org"]
    assert organization.founding_date is not None
    assert organization.dissolution_date is not None
    assert organization.founding_date.isoformat() == "2019-03-01"
    assert organization.dissolution_date.isoformat() == "2020-12-01"


def test_leaves_organization_without_memberships_untouched() -> None:
    """Date derivation must not alter organisations outside the membership snapshot."""
    current = popolo(
        [
            {
                "id": "current-org",
                "name": "Current",
                "founding_date": "1999-01-01",
            },
            {"id": "other-org", "name": "Other"},
        ],
        [
            {
                "id": "member/1",
                "person_id": "uk.org.publicwhip/person/1",
                "organization_id": "other-org",
                "start_date": "2019-03-01",
                "end_date": "2020-12-01",
            },
        ],
    )
    result = set_organization_dates_from_memberships(current)

    organization = result.organizations["current-org"]
    assert organization.founding_date is not None
    assert organization.founding_date.isoformat() == "1999-01-01"
    assert organization.dissolution_date is None
