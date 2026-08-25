from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import NamedTuple
from unittest.mock import Mock

import pytest
from mysoc_validator import Popolo

from pyscraper.committees.parliaments.westminster.client import (
    QueryParameter,
    WestminsterClient,
    batches,
)
from pyscraper.committees.parliaments.westminster.models import (
    CommitteeMembership,
    CommitteeMetadata,
    CommitteeRole,
    Post,
)
from pyscraper.committees.parliaments.westminster.parsing import (
    normalized_committee_roles,
    parse_committee_memberships,
    parse_mnis_posts,
)
from pyscraper.committees.parliaments.westminster.scraper import (
    cached_committee_metadata,
    roles_to_popolo,
)


class FakeResponse:
    """
    Minimal successful response used by the pacing test.
    """

    content = b""

    def json(self) -> object:
        """
        Return an empty decoded response body.
        """
        return []

    def raise_for_status(self) -> None:
        pass


class RequestCall(NamedTuple):
    """
    One HTTP call recorded by FakeSession.
    """

    url: str
    timeout: int
    params: list[QueryParameter] | None


class FakeSession:
    """
    Record HTTP calls made by WestminsterClient.
    """

    def __init__(self) -> None:
        self.calls: list[RequestCall] = []

    def get(
        self,
        url: str,
        *,
        timeout: int,
        params: list[QueryParameter] | None,
    ) -> FakeResponse:
        self.calls.append(RequestCall(url, timeout, params))
        return FakeResponse()


@pytest.fixture
def people() -> Popolo:
    return Popolo.model_validate(
        {
            "persons": [
                {
                    "id": "uk.org.publicwhip/person/123",
                    "identifiers": [{"identifier": "172", "scheme": "datadotparl_id"}],
                    "other_names": [
                        {
                            "given_name": "Jane",
                            "family_name": "Doe",
                            "note": "Main",
                        }
                    ],
                }
            ]
        },
        context={"skip_cross_checks": True},
    )


def test_parses_bulk_posts_and_filters_pre_2010_history() -> None:
    """The MNIS parser must prefer Hansard names and exclude pre-2010 tenures."""
    posts = parse_mnis_posts(
        b"""
        <Members>
          <Member Member_Id="172">
            <GovernmentPosts>
              <GovernmentPost Id="10">
                <Name>Fallback name</Name>
                <HansardName>The Example Minister</HansardName>
                <StartDate>2010-05-01T00:00:00</StartDate>
                <EndDate>2011-01-01T00:00:00</EndDate>
              </GovernmentPost>
              <GovernmentPost Id="11">
                <Name>Too old</Name>
                <HansardName />
                <StartDate>2008-01-01T00:00:00</StartDate>
                <EndDate>2010-05-06T00:00:00</EndDate>
              </GovernmentPost>
            </GovernmentPosts>
          </Member>
        </Members>
        """
    )
    assert posts == [
        Post(
            172,
            "GovernmentPost",
            10,
            "The Example Minister",
            date(2010, 5, 1),
            date(2011, 1, 1),
        )
    ]


def test_parses_committee_history() -> None:
    """The committee-history parser must retain nested roles and convert their dates."""
    memberships = parse_committee_memberships(
        [
            {
                "id": 172,
                "memberInfo": {"mnisId": 172},
                "committees": [
                    {
                        "id": 83,
                        "name": "Home Affairs Committee",
                        "roles": [
                            {
                                "startDate": "2019-01-01T00:00:00",
                                "endDate": None,
                                "role": {"name": "Member", "isChair": False},
                            }
                        ],
                    }
                ],
            }
        ]
    )
    assert memberships == [
        CommitteeMembership(
            member_id=172,
            committee_id=83,
            committee_name="Home Affairs Committee",
            roles=[CommitteeRole("Member", False, date(2019, 1, 1), None)],
            metadata=CommitteeMetadata(
                id=83,
                name="Home Affairs Committee",
                external_url="https://committees.parliament.uk/committee/83/",
            ),
        )
    ]


def test_chair_role_overrides_member_without_overlapping_output() -> None:
    """Chair intervals must replace overlapping generic-member intervals cleanly."""
    roles = normalized_committee_roles(
        [
            CommitteeRole("Member", False, date(2010, 5, 1), date(2020, 1, 1)),
            CommitteeRole("Chair", True, date(2015, 1, 1), date(2017, 1, 1)),
        ]
    )
    assert roles == [
        CommitteeRole(None, False, date(2010, 5, 1), date(2015, 1, 1)),
        CommitteeRole("Chair", True, date(2015, 1, 1), date(2017, 1, 1)),
        CommitteeRole(None, False, date(2017, 1, 1), date(2020, 1, 1)),
    ]


def test_builds_legacy_compatible_popolo(people: Popolo) -> None:
    """The converter must deduplicate posts and preserve legacy IDs and metadata."""
    post = Post(
        172,
        "OppositionPost",
        20,
        "Shadow Example Minister",
        date(2012, 1, 1),
        date(2014, 1, 1),
    )
    committee = CommitteeMembership(
        172,
        83,
        "Home Affairs Committee",
        [CommitteeRole("Member", False, date(2015, 1, 1), None)],
        CommitteeMetadata(
            id=83,
            name="Home Affairs Committee",
            house="Commons",
            parent_id=82,
            categories=(
                "Select",
                "(HC) Public Standing Orders - Departmental",
            ),
            description="Scrutinises the Home Office.",
            external_url="https://committees.parliament.uk/committee/83/",
        ),
    )
    result = roles_to_popolo(
        [post, post],
        [committee],
        people,
        committee_metadata={
            82: CommitteeMetadata(
                id=82,
                name="Home Affairs Parent Committee",
                house="Commons",
                external_url="https://committees.parliament.uk/committee/82/",
            )
        },
    )
    # Membership mapping deduplicates the repeated post and retains legacy IDs.
    assert len(result.memberships.root) == 2
    opposition = result.memberships["uk.parliament.data/Member/172/OppositionPost/20"]
    committee_membership = result.memberships[
        "uk.parliament.data/Member/172/Committee/83"
    ]
    assert opposition.person_id == "uk.org.publicwhip/person/123"
    assert opposition.role == "Shadow Example Minister"
    assert committee_membership.organization_id == "home-affairs-committee"
    # Organisation mapping carries hierarchy and public committee metadata across.
    organization = result.organizations["home-affairs-committee"]
    assert organization.classification == "committee"
    assert organization.parent_id == "home-affairs-parent-committee"
    assert "home-affairs-parent-committee" in result.organizations
    assert organization.description == "Scrutinises the Home Office."
    assert organization.links == ["https://committees.parliament.uk/committee/83/"]
    assert organization.extra is not None
    assert organization.get_extra("tags") == [
        "Select",
        "(HC) Public Standing Orders - Departmental",
    ]
    assert committee_membership.role is None


def test_warns_about_unresolved_mnis_people(people: Popolo) -> None:
    """Unknown MNIS IDs must produce an actionable warning and no bad membership."""
    post = Post(
        999,
        "GovernmentPost",
        20,
        "Example Minister",
        date(2024, 1, 1),
        None,
    )
    with pytest.warns(UserWarning, match="Skipping unresolved MNIS people: 999"):
        result = roles_to_popolo([post], [], people)
    assert len(result.memberships) == 0


def test_reads_cached_metadata_and_skips_detail_request(tmp_path: Path) -> None:
    """Cached committee details must avoid HTTP unless a full refresh is requested."""
    output_path = tmp_path / "westminster.json"
    output_path.write_text(
        json.dumps(
            {
                "organizations": [
                    {
                        "id": "parent-committee",
                        "name": "Parent Committee",
                        "classification": "committee",
                        "links": ["https://committees.parliament.uk/committee/82/"],
                    },
                    {
                        "id": "example-committee",
                        "name": "Example Committee",
                        "classification": "committee",
                        "description": "Cached purpose.",
                        "parent_id": "parent-committee",
                        "links": ["https://committees.parliament.uk/committee/83/"],
                        "extra": {"tags": ["Select"]},
                    },
                ]
            }
        )
    )
    cached = cached_committee_metadata(output_path)

    assert cached[83].description == "Cached purpose."
    assert cached[83].parent_id == 82
    assert cached[83].categories == ("Select",)

    membership = CommitteeMembership(
        172,
        83,
        "Example Committee",
        [CommitteeRole("Member", False, date(2024, 1, 1), None)],
        CommitteeMetadata(
            id=83,
            name="Example Committee",
            house="Commons",
        ),
    )
    client = WestminsterClient(request_delay=0)
    session = FakeSession()
    client.session = session
    details = client.committee_details([membership], cached_metadata=cached)

    assert details[83].description == "Cached purpose."
    assert session.calls == []

    response = Mock()
    response.json.return_value = {
        "id": 83,
        "name": "Example Committee",
        "house": "Commons",
        "endDate": None,
        "purpose": "<p>Fresh purpose.</p>",
    }
    get = Mock(return_value=response)
    setattr(client, "get", get)
    refreshed = client.committee_details(
        [membership],
        cached_metadata=cached,
        full_refresh=True,
    )
    assert refreshed[83].description == "Fresh purpose."
    get.assert_called_once()


def test_batches_and_pauses_between_requests() -> None:
    """Bulk requests must retain batching and pacing safeguards for upstream APIs."""
    assert list(batches([1, 2, 3], 2)) == [[1, 2], [3]]
    sleeps: list[float] = []
    client = WestminsterClient(request_delay=3, sleeper=sleeps.append)
    session = FakeSession()
    client.session = session
    client.get("https://example.test/one")
    client.get("https://example.test/two")
    assert sleeps == [3]
    assert session.calls[0].timeout == 120
