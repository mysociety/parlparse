from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from unittest.mock import Mock

import pytest
from mysoc_validator import Popolo

from pyscraper.committees.helpers.http import HttpClient
from pyscraper.committees.parliaments.scotland.models import (
    Committee,
    CommitteeData,
    CommitteeRole,
    GovernmentRole,
    MemberGovernmentRole,
    PersonCommitteeRole,
    ScottishPerson,
)
from pyscraper.committees.parliaments.scotland.parsing import parse_committee_links
from pyscraper.committees.parliaments.scotland.scraper import (
    COMMITTEE_INDEX_URL,
    cached_committee_links,
    committees_to_popolo,
    fetch_committee_data,
    person_for_scottish_id,
    refreshed_committee_links,
)


@pytest.fixture
def people() -> Popolo:
    return Popolo.model_validate(
        {
            "organizations": [
                {"id": "scottish-parliament", "name": "Scottish Parliament"}
            ],
            "posts": [
                {
                    "id": "uk.org.publicwhip/cons/80001",
                    "organization_id": "scottish-parliament",
                    "area": {"name": "Example constituency"},
                    "label": "Member of the Scottish Parliament",
                    "role": "MSP",
                }
            ],
            "persons": [
                {
                    "id": "uk.org.publicwhip/person/123",
                    "identifiers": [{"identifier": "456", "scheme": "scotparl_id"}],
                    "other_names": [
                        {
                            "given_name": "Jane",
                            "family_name": "Doe",
                            "note": "Main",
                        }
                    ],
                },
                {
                    "id": "uk.org.publicwhip/person/124",
                    "other_names": [
                        {
                            "given_name": "Jane",
                            "family_name": "Doe",
                            "note": "Main",
                        }
                    ],
                },
            ],
            "memberships": [
                {
                    "id": "uk.org.publicwhip/member/80001",
                    "person_id": "uk.org.publicwhip/person/123",
                    "post_id": "uk.org.publicwhip/cons/80001",
                    "start_date": "2021-01-01",
                }
            ],
        }
    )


def test_reads_cached_links_and_skips_index_request(tmp_path: Path) -> None:
    """The client must reuse saved public URLs instead of fetching the HTML index."""
    output_path = tmp_path / "scotland.json"
    output_path.write_text(
        json.dumps(
            {
                "organizations": [
                    {
                        "id": "scottish-parliament-committee-99",
                        "name": "Example Committee",
                        "classification": "committee",
                        "links": [
                            "https://www.parliament.scot/chamber-and-committees/"
                            "committees/current-and-previous-committees/"
                            "session-7/example-committee"
                        ],
                    }
                ]
            }
        )
    )
    cached = cached_committee_links(output_path)

    assert cached == {
        "Example Committee": (
            "https://www.parliament.scot/chamber-and-committees/"
            "committees/current-and-previous-committees/"
            "session-7/example-committee"
        )
    }
    client = HttpClient()
    setattr(client, "get_json", Mock(return_value=[]))
    cached_get_text = Mock()
    setattr(client, "get_text", cached_get_text)
    with pytest.raises(ValueError, match="committees returned no records"):
        fetch_committee_data(client, cached)
    cached_get_text.assert_not_called()

    refreshed_get_text = Mock(
        return_value=(
            '<a href="/chamber-and-committees/committees/'
            'current-and-previous-committees/session-7/example-committee">'
            "Example Committee</a>"
        )
    )
    setattr(client, "get_text", refreshed_get_text)
    assert refreshed_committee_links(client) == cached
    refreshed_get_text.assert_called_once()


def test_parses_public_committee_links() -> None:
    """The HTML index parser must map committee names to absolute public URLs."""
    links = parse_committee_links(
        """
        <a href="/chamber-and-committees/committees/current-and-previous-committees/session-7/example-committee">
          Example Committee
        </a>
        """,
        COMMITTEE_INDEX_URL,
    )
    assert links["Example Committee"] == (
        "https://www.parliament.scot/chamber-and-committees/committees/"
        "current-and-previous-committees/session-7/example-committee"
    )


def test_end_dates_are_exclusive() -> None:
    """Scottish API valid-until dates must exclude an entity on that exact date."""
    committee = Committee(
        id=99,
        name="Example Committee",
        valid_from=datetime(2024, 1, 1),
        valid_until=datetime(2024, 2, 1),
    )
    assert committee.active_on(date(2024, 1, 31))
    assert not committee.active_on(date(2024, 2, 1))


def test_builds_current_supplemental_popolo(people: Popolo) -> None:
    """The converter must join source tables, filter ended committees, and map roles."""
    data = CommitteeData(
        committees=[
            Committee(
                id=99,
                name="Example Committee",
                description=" Example remit.\r\n",
                blog_website="https://example.test/blog",
                valid_from=datetime(2021, 1, 1),
            ),
            Committee(
                id=98,
                name="Former Committee",
                valid_from=datetime(2016, 1, 1),
                valid_until=datetime(2021, 1, 1),
            ),
        ],
        roles=[
            CommitteeRole(id=1, name="Member"),
            CommitteeRole(id=3, name="Convener"),
        ],
        person_roles=[
            PersonCommitteeRole(
                id=1001,
                person_id=456,
                committee_role_id=3,
                committee_id=99,
                valid_from=datetime(2021, 1, 1),
            ),
            PersonCommitteeRole(
                id=1000,
                person_id=456,
                committee_role_id=1,
                committee_id=98,
                valid_from=datetime(2016, 1, 1),
                valid_until=datetime(2021, 1, 1),
            ),
        ],
        government_roles=[GovernmentRole(id=10, name="Cabinet Secretary for Examples")],
        member_government_roles=[
            MemberGovernmentRole(
                id=2001,
                person_id=456,
                government_role_id=10,
                valid_from=datetime(2022, 2, 3),
                valid_until=datetime(2023, 4, 5),
            )
        ],
        committee_links={"Example Committee": "https://example.test/committee"},
    )
    result = committees_to_popolo(
        data=data,
        people=people,
        membership_date=date(2024, 1, 1),
    )
    # Active-committee mapping: ended committees and their roles are excluded.
    organization = result.organizations.root[0]
    membership = result.memberships["parliament.scot/Committee/99/Member/456"]
    assert len(result.organizations) == 1
    assert {item.id for item in result.organizations} == {
        "scottish-parliament-committee-99"
    }
    assert {item.id for item in result.memberships} == {
        "parliament.scot/Committee/99/Member/456",
        "scot.parliament.data/membergovernmentroles/2001",
    }
    assert organization.id == "scottish-parliament-committee-99"
    assert organization.name == "Example Committee"
    assert organization.classification == "committee"
    assert organization.description == "Example remit."
    assert organization.links == [
        "https://example.test/committee",
        "https://example.test/blog",
    ]
    # Committee-role mapping: the source ID resolves to the expected TWFY person.
    assert membership.person_id == "uk.org.publicwhip/person/123"
    assert membership.role == "Convener"
    # Government-role mapping is historical, so its source dates must survive.
    government = result.memberships["scot.parliament.data/membergovernmentroles/2001"]
    assert government.person_id == "uk.org.publicwhip/person/123"
    assert government.organization_id == "scottish-parliament"
    assert government.role == "Cabinet Secretary for Examples"
    assert government.start_date.isoformat() == "2022-02-03"
    assert government.end_date.isoformat() == "2023-04-05"


def test_falls_back_from_missing_identifier_to_dated_name(people: Popolo) -> None:
    """A missing Scottish ID must fall back to a chamber-eligible name match."""
    person_id = person_for_scottish_id(
        999,
        people,
        {999: ScottishPerson(person_id=999, parliamentary_name="Doe, Ms Jane")},
        date(2024, 1, 1),
    )
    assert person_id == "uk.org.publicwhip/person/123"


def test_rejects_an_unresolved_person(people: Popolo) -> None:
    """The converter must fail loudly rather than silently omit an unknown MSP."""
    data = CommitteeData(
        committees=[
            Committee(
                id=99,
                name="Example Committee",
                valid_from=datetime(2021, 1, 1),
            )
        ],
        roles=[CommitteeRole(id=1, name="Member")],
        person_roles=[
            PersonCommitteeRole(
                id=1001,
                person_id=999,
                committee_role_id=1,
                committee_id=99,
                valid_from=datetime(2021, 1, 1),
            )
        ],
    )
    with pytest.raises(ValueError, match="Scottish Parliament person 999"):
        committees_to_popolo(
            data=data,
            people=people,
            membership_date=date(2024, 1, 1),
        )
