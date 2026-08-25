import json
from pathlib import Path
from unittest.mock import Mock

import pytest
from mysoc_validator import Popolo

from pyscraper.committees.parliaments.northern_ireland.client import (
    MINISTERIAL_ROLE_TYPE,
    NorthernIrelandAssemblyClient,
)
from pyscraper.committees.parliaments.northern_ireland.models import (
    AssemblyPerson,
    Committee,
    MemberRole,
)
from pyscraper.committees.parliaments.northern_ireland.parsing import (
    parse_committee_links,
    parse_committees,
    parse_member_roles,
)
from pyscraper.committees.parliaments.northern_ireland.scraper import (
    COMMITTEE_ROLE_TYPE,
    cached_committee_links,
    cached_government_memberships,
    committees_to_popolo,
    government_memberships,
    normalize_ministerial_boundaries,
    person_id_for_ni_role,
)


@pytest.fixture
def people() -> Popolo:
    return Popolo.model_validate(
        {
            "organizations": [
                {"id": "northern-ireland-assembly", "name": "NI Assembly"}
            ],
            "posts": [
                {
                    "id": "uk.org.publicwhip/cons/90001",
                    "organization_id": "northern-ireland-assembly",
                    "area": {"name": "Example constituency"},
                    "label": "Member of the Legislative Assembly",
                    "role": "MLA",
                }
            ],
            "persons": [
                {
                    "id": "uk.org.publicwhip/person/123",
                    "identifiers": [
                        {
                            "identifier": "456",
                            "scheme": "data.niassembly.gov.uk",
                        }
                    ],
                    "other_names": [
                        {
                            "given_name": "Jane",
                            "family_name": "Doe",
                            "note": "Main",
                        }
                    ],
                }
            ],
            "memberships": [
                {
                    "id": "uk.org.publicwhip/member/90001",
                    "person_id": "uk.org.publicwhip/person/123",
                    "post_id": "uk.org.publicwhip/cons/90001",
                    "start_date": "2022-01-01",
                }
            ],
        }
    )


def test_reads_cached_links_and_skips_index_request(tmp_path: Path) -> None:
    """The client must reuse saved public URLs instead of fetching the HTML index."""
    output_path = tmp_path / "northern-ireland.json"
    output_path.write_text(
        json.dumps(
            {
                "organizations": [
                    {
                        "id": "ni-assembly-committee-99",
                        "name": "Committee for Health",
                        "classification": "committee",
                        "links": [
                            "https://www.niassembly.gov.uk/"
                            "assembly-business/committees/2022-2027/health/"
                        ],
                    }
                ]
            }
        )
    )
    cached = cached_committee_links(output_path)

    assert cached == {
        "health": (
            "https://www.niassembly.gov.uk/"
            "assembly-business/committees/2022-2027/health/"
        )
    }
    client = NorthernIrelandAssemblyClient()
    setattr(
        client,
        "get_object",
        Mock(
            side_effect=lambda url: (
                {"AllMembersRoles": {"Role": []}}
                if "GetAllMemberRoles" in url
                else {"OrganisationsList": {"Organisation": []}}
            )
        ),
    )
    cached_get_text = Mock()
    setattr(client, "get_text", cached_get_text)
    assembly_data = client.all_data(cached)
    assert assembly_data.committees == [] and assembly_data.roles == []
    cached_get_text.assert_not_called()

    refreshed_get_text = Mock(return_value="")
    setattr(client, "get_text", refreshed_get_text)
    assembly_data = client.all_data(None)
    assert assembly_data.committees == [] and assembly_data.roles == []
    refreshed_get_text.assert_called_once()


def test_parses_public_committee_links() -> None:
    """The HTML index parser must turn a committee page link into a slug lookup."""
    links = parse_committee_links(
        """
        <a href="/assembly-business/committees/2022-2027/health/">
          Health
        </a>
        """
    )
    assert links["health"] == (
        "https://www.niassembly.gov.uk/assembly-business/committees/2022-2027/health/"
    )


def test_parses_committee_api_response() -> None:
    """The organisations feed parser must coerce IDs and clean source text."""
    committees = parse_committees(
        {
            "OrganisationsList": {
                "Organisation": {
                    "OrganisationId": "99",
                    "OrganisationName": " Example Committee ",
                    "OrganisationType": "Standing Committee",
                }
            }
        },
        "https://example.test/committees",
    )
    assert committees == [Committee(99, "Example Committee", "Standing Committee")]


def test_parses_member_role_api_response() -> None:
    """The member-role feed parser must map nested records to role objects."""
    roles = parse_member_roles(
        {
            "AllMembersRoles": {
                "Role": [
                    {
                        "AffiliationId": "1001",
                        "PersonId": "456",
                        "RoleType": COMMITTEE_ROLE_TYPE,
                        "Role": "Committee Chair",
                        "OrganisationId": "99",
                    }
                ]
            }
        }
    )
    assert roles == [MemberRole(1001, 456, COMMITTEE_ROLE_TYPE, "Committee Chair", 99)]


def test_builds_current_supplemental_popolo(people: Popolo) -> None:
    """The converter must join current committee roles and discard unrelated ones."""
    result = committees_to_popolo(
        [
            Committee(
                99,
                "Example Committee",
                "Standing Committee",
                "https://example.test/committee",
            )
        ],
        [
            MemberRole(1001, 456, COMMITTEE_ROLE_TYPE, "Committee Chair", 99),
            MemberRole(1002, 456, "Political Party Role", "Party Member", 99),
            MemberRole(1003, 456, COMMITTEE_ROLE_TYPE, "Committee Member", 98),
        ],
        people,
    )
    # Committee mapping: source metadata becomes the stable public organisation.
    organization = result.organizations.root[0]
    membership = result.memberships["niassembly.gov.uk/Committee/99/Member/456"]
    assert organization.id == "ni-assembly-committee-99"
    assert organization.name == "Example Committee"
    assert organization.classification == "committee"
    assert organization.links == ["https://example.test/committee"]
    assert organization.extra is not None
    assert organization.get_extra("tags") == ["Standing Committee"]
    # Role filtering and person resolution: only the matching committee role survives.
    assert len(result.memberships) == 1
    assert membership.person_id == "uk.org.publicwhip/person/123"
    assert membership.role == "Committee Chair"


def test_builds_historical_ministerial_memberships(people: Popolo) -> None:
    """Ministerial history must retain source dates and create its department post."""
    roles = parse_member_roles(
        {
            "AllMembersRoles": {
                "Role": [
                    {
                        "AffiliationId": "2001",
                        "PersonId": "456",
                        "RoleType": "Ministerial Role",
                        "Role": "Minister",
                        "OrganisationId": "82",
                        "Organisation": "Department of Health",
                        "AffiliationStart": "2021-06-14T00:00:00+01:00",
                        "AffiliationEnd": "2022-10-27T00:00:00+01:00",
                        "AffiliationTitle": "Minister of Health",
                    }
                ]
            }
        },
        "https://example.test/roles",
    )
    memberships = government_memberships(
        roles,
        people,
        {},
    )
    membership = memberships[0]
    result = committees_to_popolo(
        [Committee(99, "Example Committee", "Standing Committee")],
        [],
        people,
        memberships,
    )
    # Ministerial mapping: source history becomes a dated membership and post.
    membership = result.memberships["niassembly.gov.uk/Affiliation/2001"]
    assert membership.id == "niassembly.gov.uk/Affiliation/2001"
    assert membership.role == "Minister of Health"
    assert membership.post_id == (
        "niassembly.gov.uk/Department/82/Post/minister-of-health"
    )
    assert membership.post_id is not None
    post = result.posts[membership.post_id]
    assert post.organization_id == "northern-ireland-executive"
    assert post.label == "Minister of Health"
    assert membership.start_date.isoformat() == "2021-06-14"
    assert membership.end_date.isoformat() == "2022-10-27"
    assert membership.extra is not None
    assert membership.extra.model_dump(exclude_none=True, exclude_defaults=True) == {
        "tags": ["Ministerial Role"],
        "department_id": 82,
        "department": "Department of Health",
    }


def test_normalizes_same_day_ministerial_handovers(people: Popolo) -> None:
    """Assembly midnight boundaries must not overlap as inclusive Popolo dates."""
    memberships = government_memberships(
        [
            MemberRole(
                2001,
                456,
                "Ministerial Role",
                "Minister",
                82,
                "Department of Health",
                "Minister of Health",
                "2021-06-14",
                "2022-10-27",
            ),
            MemberRole(
                2002,
                456,
                "Ministerial Role",
                "Minister",
                82,
                "Department of Health",
                "Minister of Health",
                "2022-10-27",
                None,
            ),
        ],
        people,
        {},
    )

    normalized = normalize_ministerial_boundaries(memberships)

    assert normalized[0].end_date.isoformat() == "2022-10-26"
    assert normalized[1].start_date.isoformat() == "2022-10-27"


def test_empty_previous_government_cache_triggers_initial_discovery(
    tmp_path: Path,
) -> None:
    """An empty first-run output must not suppress discovery of ministerial history."""
    output_path = tmp_path / "northern-ireland.json"
    output_path.write_text(json.dumps({"memberships": []}))
    assert cached_government_memberships(output_path) is None


def test_resolves_later_lord_name_for_historical_ni_membership() -> None:
    """Historical NI roles must resolve a person named by their later peerage title."""
    people = Popolo.model_validate(
        {
            "organizations": [
                {"id": "house-of-lords", "name": "House of Lords"},
                {
                    "id": "northern-ireland-assembly",
                    "name": "Northern Ireland Assembly",
                },
            ],
            "posts": [
                {
                    "id": "uk.org.publicwhip/cons/999",
                    "organization_id": "northern-ireland-assembly",
                    "label": "Member of the Legislative Assembly",
                    "role": "MLA",
                }
            ],
            "persons": [
                {
                    "id": "uk.org.publicwhip/person/999",
                    "other_names": [
                        {
                            "given_name": "Nigel",
                            "family_name": "Dodds",
                            "note": "Main",
                            "start_date": "1998-01-01",
                            "end_date": "2020-09-17",
                        },
                        {
                            "given_name": "Nigel",
                            "honorific_prefix": "Lord",
                            "lordname": "Dodds",
                            "lordofname": "Duncairn",
                            "note": "Main",
                            "start_date": "2020-09-18",
                        },
                    ],
                }
            ],
            "memberships": [
                {
                    "id": "uk.org.publicwhip/member/999",
                    "person_id": "uk.org.publicwhip/person/999",
                    "post_id": "uk.org.publicwhip/cons/999",
                    "start_date": "1998-01-01",
                    "end_date": "2003-11-26",
                },
                {
                    "id": "uk.org.publicwhip/lord/999",
                    "organization_id": "house-of-lords",
                    "person_id": "uk.org.publicwhip/person/999",
                    "start_date": "2020-09-18",
                },
            ],
        }
    )
    record = MemberRole(
        2001,
        999,
        MINISTERIAL_ROLE_TYPE,
        "Minister",
        82,
        start_date="2001-01-01",
    )

    assert (
        person_id_for_ni_role(
            record,
            people,
            {999: AssemblyPerson(999, "Lord Dodds of Duncairn")},
        )
        == "uk.org.publicwhip/person/999"
    )


def test_rejects_an_unresolved_person(people: Popolo) -> None:
    """The converter must fail loudly rather than silently omit an unknown MLA."""
    with pytest.raises(ValueError, match="NI Assembly person 999"):
        committees_to_popolo(
            [Committee(99, "Example Committee", "Standing Committee")],
            [MemberRole(1001, 999, COMMITTEE_ROLE_TYPE, "Committee Member", 99)],
            people,
        )
