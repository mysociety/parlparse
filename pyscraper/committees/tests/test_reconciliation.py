from __future__ import annotations

import json
from datetime import date

from mysoc_validator import Popolo
from mysoc_validator.models.popolo import Membership

from pyscraper.committees.helpers.reconciliation import (
    reconcile_snapshot_memberships,
)


def popolo(
    memberships: list[dict[str, object]],
    organizations: list[dict[str, object]] | None = None,
) -> Popolo:
    return Popolo.model_validate(
        {
            "organizations": organizations
            or [{"id": "current-org", "name": "Current"}],
            "memberships": memberships,
        },
        context={"skip_cross_checks": True},
    )


def is_snapshot(item: Membership) -> bool:
    return item.id.startswith("snapshot/")


def serialized_membership(popolo: Popolo, membership_id: str) -> dict[str, object]:
    return next(
        item
        for item in json.loads(popolo.to_json_str())["memberships"]
        if item["id"] == membership_id
    )


def test_leaves_an_unknown_start_unknown_and_source_dates_untouched() -> None:
    """A first snapshot must preserve unknown starts and authoritative history dates."""
    current = popolo(
        [
            {
                "id": "snapshot/member/101",
                "person_id": "uk.org.publicwhip/person/1",
                "organization_id": "current-org",
                "role": "Member",
            },
            {
                "id": "source/history/102",
                "person_id": "uk.org.publicwhip/person/2",
                "organization_id": "current-org",
                "start_date": "2020-01-01",
                "end_date": "2021-01-01",
            },
        ]
    )
    result = reconcile_snapshot_memberships(
        None, current, date(2026, 8, 12), is_snapshot
    )

    snapshot = result.memberships["snapshot/member/101"]
    source = result.memberships["source/history/102"]
    assert "start_date" not in serialized_membership(result, "snapshot/member/101")
    assert snapshot.end_date.isoformat() == "9999-12-31"
    assert source.start_date.isoformat() == "2020-01-01"
    assert source.end_date.isoformat() == "2021-01-01"


def test_explicit_validator_sentinels_mean_unknown_start_and_open_end() -> None:
    """Validator sentinel dates must not be mistaken for real tenure boundaries."""
    previous = popolo(
        [
            {
                "id": "snapshot/member/101",
                "person_id": "uk.org.publicwhip/person/1",
                "organization_id": "current-org",
                "start_date": "0001-01-01",
                "end_date": "9999-12-31",
            }
        ]
    )
    current = popolo(
        [
            {
                "id": "snapshot/member/101",
                "person_id": "uk.org.publicwhip/person/1",
                "organization_id": "current-org",
            }
        ]
    )

    result = reconcile_snapshot_memberships(
        previous, current, date(2026, 8, 12), is_snapshot
    )

    membership = serialized_membership(result, "snapshot/member/101")
    assert "start_date" not in membership
    assert "end_date" not in membership


def test_retains_the_first_seen_date_and_uses_current_fields() -> None:
    """An ongoing tenure keeps its original start while accepting current role data."""
    previous = popolo(
        [
            {
                "id": "snapshot/member/101",
                "person_id": "uk.org.publicwhip/person/1",
                "organization_id": "current-org",
                "role": "Member",
                "start_date": "2026-08-01",
            }
        ]
    )
    current = popolo(
        [
            {
                "id": "snapshot/member/101",
                "person_id": "uk.org.publicwhip/person/1",
                "organization_id": "current-org",
                "role": "Chair",
            }
        ]
    )
    result = reconcile_snapshot_memberships(
        previous, current, date(2026, 8, 12), is_snapshot
    )

    membership = result.memberships["snapshot/member/101"]
    assert membership.start_date.isoformat() == "2026-08-01"
    assert membership.role == "Chair"


def test_stable_source_id_survives_a_person_record_merge() -> None:
    """A changed TWFY person ID must update one tenure, not close and duplicate it."""
    previous = popolo(
        [
            {
                "id": "snapshot/member/101",
                "person_id": "uk.org.publicwhip/person/1",
                "organization_id": "current-org",
            }
        ]
    )
    current = popolo(
        [
            {
                "id": "snapshot/member/101",
                "person_id": "uk.org.publicwhip/person/2",
                "organization_id": "current-org",
            }
        ]
    )
    result = reconcile_snapshot_memberships(
        previous, current, date(2026, 8, 12), is_snapshot
    )

    assert len(result.memberships) == 1
    membership = result.memberships["snapshot/member/101"]
    assert membership.person_id == "uk.org.publicwhip/person/2"
    assert "start_date" not in serialized_membership(result, "snapshot/member/101")
    assert "end_date" not in serialized_membership(result, "snapshot/member/101")


def test_closes_a_missing_membership_yesterday_and_retains_its_organization() -> None:
    """A vanished tenure must close yesterday without dropping its former committee."""
    previous = popolo(
        [
            {
                "id": "snapshot/member/101",
                "person_id": "uk.org.publicwhip/person/1",
                "organization_id": "former-org",
                "start_date": "2026-08-01",
            }
        ],
        [{"id": "former-org", "name": "Former"}],
    )
    current = popolo([], [{"id": "current-org", "name": "Current"}])
    result = reconcile_snapshot_memberships(
        previous, current, date(2026, 8, 12), is_snapshot
    )

    membership = result.memberships["snapshot/member/101"]
    assert membership.end_date.isoformat() == "2026-08-11"
    assert result.organizations["former-org"].name == "Former"
    assert result.organizations["current-org"].name == "Current"


def test_closes_a_missing_membership_without_inventing_its_start() -> None:
    """Closing a tenure must not manufacture a start date absent from prior output."""
    previous = popolo(
        [
            {
                "id": "snapshot/member/101",
                "person_id": "uk.org.publicwhip/person/1",
                "organization_id": "current-org",
            }
        ]
    )
    result = reconcile_snapshot_memberships(
        previous, popolo([]), date(2026, 8, 12), is_snapshot
    )

    membership = serialized_membership(result, "snapshot/member/101")
    assert "start_date" not in membership
    assert membership["end_date"] == "2026-08-11"


def test_rejoining_after_a_closed_tenure_allocates_a_new_id() -> None:
    """A returning member must get a new tenure without reopening the old record."""
    previous = popolo(
        [
            {
                "id": "snapshot/member/101",
                "person_id": "uk.org.publicwhip/person/1",
                "organization_id": "current-org",
                "start_date": "2026-07-01",
                "end_date": "2026-07-31",
            }
        ]
    )
    current = popolo(
        [
            {
                "id": "snapshot/member/101",
                "person_id": "uk.org.publicwhip/person/1",
                "organization_id": "current-org",
            }
        ]
    )
    result = reconcile_snapshot_memberships(
        previous, current, date(2026, 8, 12), is_snapshot
    )

    assert len(result.memberships) == 2
    assert (
        result.memberships["snapshot/member/101"].end_date.isoformat() == "2026-07-31"
    )
    rejoined = result.memberships["snapshot/member/101/2"]
    assert "start_date" not in serialized_membership(result, "snapshot/member/101/2")
    assert rejoined.end_date.isoformat() == "9999-12-31"


def test_keeps_an_existing_active_membership_start_unknown() -> None:
    """Repeated snapshots must not turn an unknown start into a first-seen date."""
    previous = popolo(
        [
            {
                "id": "snapshot/member/101",
                "person_id": "uk.org.publicwhip/person/1",
                "organization_id": "current-org",
            }
        ]
    )
    current = popolo(
        [
            {
                "id": "snapshot/member/101",
                "person_id": "uk.org.publicwhip/person/1",
                "organization_id": "current-org",
            }
        ]
    )
    result = reconcile_snapshot_memberships(
        previous, current, date(2026, 8, 12), is_snapshot
    )
    assert "start_date" not in serialized_membership(result, "snapshot/member/101")
