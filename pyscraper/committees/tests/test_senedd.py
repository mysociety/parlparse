import json
from datetime import date

from bs4 import BeautifulSoup
from mysoc_validator import Popolo

from pyscraper.committees.parliaments.senedd.models import (
    BilingualCommittee,
    Committee,
    CommitteeSummary,
    GovernmentMember,
    MemberCard,
)
from pyscraper.committees.parliaments.senedd.parsing import (
    is_current_committee,
    normalize_member_name,
    parse_committee_list,
    parse_committee_page,
    parse_government_members,
    parse_member_cards,
    parse_members_csv,
)
from pyscraper.committees.parliaments.senedd.scraper import (
    ENGLISH,
    WELSH,
    committees_to_popolo,
    pair_government_members,
    person_id_for_member,
)

COMMITTEE_HTML = """
<div class="person-search-result-item">
  <a href="/people/jane-doe-ms/">
    <img data-src="https://example.test/UserData/Info00012345/bigpic.jpg">
    <p class="person-search-result-item__text">Jane Doe MS</p>
    <p class="person-search-result-item__text -bold">Chair</p>
  </a>
</div>
"""
COMMITTEE_PAGE_HTML = f"""
<a href="/Umbraco/Api/Committee/DownloadCommitteeMembersCsv?committeeId=210781&amp;cultureInfo=en-GB">
  Download
</a>
<h2>Remit</h2>
<p>Scrutinise finance.</p>
<h2>Committee Members</h2>
{COMMITTEE_HTML}
"""
COMMITTEES_XML = b"""<?xml version="1.0" encoding="utf-8"?>
<committees>
  <committeescount>4</committeescount>
  <committee>
    <committeeid>984</committeeid>
    <committeetitle>Finance Committee</committeetitle>
    <committeedeleted>False</committeedeleted>
    <committeeexpired>False</committeeexpired>
    <committeecategory>Committees</committeecategory>
  </committee>
  <committee>
    <committeeid>329</committeeid>
    <committeetitle>Finance Committee - Fifth Senedd</committeetitle>
    <committeedeleted>False</committeedeleted>
    <committeeexpired>True</committeeexpired>
    <committeecategory>Committees</committeecategory>
  </committee>
  <committee>
    <committeeid>330</committeeid>
    <committeetitle>Historic Committee</committeetitle>
    <committeedeleted>True</committeedeleted>
    <committeeexpired>False</committeeexpired>
    <committeecategory>Committees</committeecategory>
  </committee>
  <committee>
    <committeeid>331</committeeid>
    <committeetitle>Unrelated Body</committeetitle>
    <committeedeleted>False</committeedeleted>
    <committeeexpired>False</committeeexpired>
    <committeecategory>Other Bodies</committeecategory>
  </committee>
</committees>
"""


def test_normalize_member_name_accepts_both_api_suffixes() -> None:
    """Name matching must strip both English and Welsh member suffixes."""
    assert normalize_member_name("Jane Doe MS") == "Jane Doe"
    assert normalize_member_name("Jane Doe AS") == "Jane Doe"


def test_member_resolution_prefers_the_official_identifier() -> None:
    """A Senedd source ID must resolve a member even when display names disagree."""
    people = Popolo.model_validate(
        {
            "persons": [
                {
                    "id": "uk.org.publicwhip/person/123",
                    "identifiers": [{"identifier": "12345", "scheme": "senedd"}],
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
    person_id = person_id_for_member(
        MemberCard("A different display name", "Member", "12345"),
        people,
        date(2026, 8, 12),
    )
    assert person_id == "uk.org.publicwhip/person/123"


def test_parse_member_cards_extracts_role_and_senedd_id() -> None:
    """Committee-page cards must yield the role and ID embedded in their markup."""
    members = parse_member_cards(BeautifulSoup(COMMITTEE_HTML, "html.parser"))
    assert members["Jane Doe"] == MemberCard(
        name="Jane Doe MS", role="Chair", senedd_id="12345"
    )


def test_parse_committee_list_filters_current_categories() -> None:
    """ModernGov XML flags must distinguish a current committee from an expired one."""
    summaries = parse_committee_list(COMMITTEES_XML)
    assert summaries[0] == CommitteeSummary(
        modern_gov_id="984",
        name="Finance Committee",
        deleted=False,
        expired=False,
        category="Committees",
    )
    assert is_current_committee(summaries[0], ENGLISH)
    assert not is_current_committee(summaries[1], ENGLISH)
    assert not is_current_committee(summaries[2], ENGLISH)
    assert not is_current_committee(summaries[3], ENGLISH)


def test_constructs_language_pages_and_member_csv_urls() -> None:
    """Each language configuration must target its own page and CSV endpoints."""
    assert ENGLISH.committee_url("984") == "https://senedd.wales/committee/984"
    assert WELSH.committee_url("984") == "https://senedd.cymru/pwyllgor/984"
    assert ENGLISH.members_csv_url("210781") == (
        "https://senedd.wales/Umbraco/Api/Committee/"
        "DownloadCommitteeMembersCsv?committeeId=210781&cultureInfo=en-GB"
    )
    assert WELSH.members_csv_url("210781") == (
        "https://senedd.cymru/Umbraco/Api/Committee/"
        "DownloadCommitteeMembersCsv?committeeId=210781&cultureInfo=cy-GB"
    )


def test_parse_committee_page_uses_api_name_and_internal_id() -> None:
    """The page parser must combine ModernGov metadata with Umbraco-only fields."""
    summary = CommitteeSummary(
        modern_gov_id="984",
        name="Finance Committee",
        deleted=False,
        expired=False,
        category="Committees",
    )
    committee = parse_committee_page(
        summary,
        ENGLISH.committee_url(summary.modern_gov_id),
        COMMITTEE_PAGE_HTML,
        ENGLISH,
    )
    assert committee.id == "210781"
    assert committee.name == "Finance Committee"
    assert committee.category == "Committees"
    assert committee.description == "Scrutinise finance."
    assert committee.csv_url == (
        "https://senedd.wales/Umbraco/Api/Committee/"
        "DownloadCommitteeMembersCsv?committeeId=210781&cultureInfo=en-GB"
    )
    assert committee.members[0].role == "Chair"


def test_parse_members_csv_combines_api_and_page_data() -> None:
    """CSV membership rows must retain IDs and roles scraped from the HTML page."""
    committee = Committee(
        "99",
        "Example Committee",
        "https://example.test/committee",
        "https://example.test/api?committeeId=99&cultureInfo=en-GB",
        [MemberCard("Jane Doe MS", "Chair", "12345")],
    )
    content = b"Name,Party\r\nJane Doe MS,Example Party\r\n"
    assert parse_members_csv(committee, content, ENGLISH) == [
        MemberCard("Jane Doe", "Chair", "12345")
    ]


def test_parse_government_members() -> None:
    """The government page parser must extract minister names, roles, and links."""
    members = parse_government_members(
        """
        <div class="key-person">
          <a href="/jane-doe-ms">
            <div class="key-person__details">
              <span>Rt Hon Jane Doe MS</span>
              <span class="subtitle">Cabinet Secretary for Examples</span>
            </div>
          </a>
        </div>
        """,
        "https://www.gov.wales/cabinet",
    )
    assert members == [
        GovernmentMember(
            "Rt Hon Jane Doe MS",
            "Cabinet Secretary for Examples",
            "https://www.gov.wales/jane-doe-ms",
        )
    ]


def test_builds_supplemental_popolo() -> None:
    """The converter must preserve bilingual committee and government semantics."""
    people = Popolo.model_validate(
        {
            "organizations": [{"id": "welsh-parliament", "name": "Welsh Parliament"}],
            "posts": [
                {
                    "id": "uk.org.publicwhip/cons/70001",
                    "organization_id": "welsh-parliament",
                    "area": {"name": "Example constituency"},
                    "label": "Member of the Senedd",
                    "role": "MS",
                }
            ],
            "persons": [
                {
                    "id": "uk.org.publicwhip/person/123",
                    "identifiers": [{"identifier": "12345", "scheme": "senedd"}],
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
                    "id": "uk.org.publicwhip/member/70001",
                    "person_id": "uk.org.publicwhip/person/123",
                    "post_id": "uk.org.publicwhip/cons/70001",
                    "start_date": "2020-01-01",
                }
            ],
        }
    )
    english_committee = Committee(
        "99",
        "Example Committee",
        "https://example.test/committee",
        "https://example.test/api?committeeId=99&cultureInfo=en-GB",
        [MemberCard("Jane Doe", "Chair", "12345")],
        "Committees",
        "English remit.",
    )
    welsh_committee = Committee(
        "99",
        "Y Pwyllgor Enghreifftiol",
        "https://example.test/cy/committee",
        "https://example.test/api?committeeId=99&cultureInfo=cy-GB",
        [MemberCard("Jane Doe", "Cadeirydd", "12345")],
        "Pwyllgorau",
        "Cylch gwaith Cymraeg.",
    )
    government = pair_government_members(
        [
            GovernmentMember(
                "Rt Hon Jane Doe MS",
                "Cabinet Secretary for Examples",
                "https://www.gov.wales/jane-doe-ms",
            )
        ],
        [
            GovernmentMember(
                "Y Gwir Anrhydeddus Jane Doe AS",
                "Ysgrifennydd y Cabinet dros Enghreifftiau",
                "https://www.llyw.cymru/jane-doe-as",
            )
        ],
        people,
        membership_date=date(2024, 1, 1),
    )
    result = committees_to_popolo(
        [BilingualCommittee(english=english_committee, welsh=welsh_committee)],
        people,
        membership_date=date(2024, 1, 1),
        government_members=government,
    )
    # Organisation mapping combines both languages without losing source metadata.
    organization = result.organizations.root[0]
    membership = result.memberships["senedd.wales/Committee/99/Member/12345"]
    assert organization.id == "senedd-committee-99"
    assert organization.classification == "committee"
    assert organization.links == [
        "https://example.test/cy/committee",
        "https://example.test/committee",
    ]
    assert organization.extra is not None
    assert organization.get_extra("tags") == ["Pwyllgorau", "Committees"]
    assert organization.description == "Cylch gwaith Cymraeg.\n\nEnglish remit."
    assert organization.name == "Y Pwyllgor Enghreifftiol / Example Committee"
    assert organization.get_localised_value("name", "cy") == "Y Pwyllgor Enghreifftiol"
    assert organization.get_localised_value("name", "en") == "Example Committee"
    assert (
        organization.get_localised_value("description", "cy") == "Cylch gwaith Cymraeg."
    )
    assert organization.get_localised_value("description", "en") == "English remit."
    # Committee membership mapping pairs the Welsh and English role labels.
    assert membership.person_id == "uk.org.publicwhip/person/123"
    assert membership.role == "Cadeirydd / Chair"
    assert membership.get_localised_value("role", "cy") == "Cadeirydd"
    assert membership.get_localised_value("role", "en") == "Chair"
    # Government membership mapping applies the same bilingual pairing.
    government_membership = result.memberships["gov.wales/Minister/123"]
    assert government_membership.role == (
        "Ysgrifennydd y Cabinet dros Enghreifftiau / Cabinet Secretary for Examples"
    )
    assert (
        government_membership.get_localised_value("role", "cy")
        == "Ysgrifennydd y Cabinet dros Enghreifftiau"
    )
    assert (
        government_membership.get_localised_value("role", "en")
        == "Cabinet Secretary for Examples"
    )
    # Wire-format checks catch localisation lost specifically during serialization.
    serialized = json.loads(result.to_json_str())
    assert serialized["organizations"][0]["extra"]["localised_values"] == {
        "name": {"cy": "Y Pwyllgor Enghreifftiol", "en": "Example Committee"},
        "description": {"cy": "Cylch gwaith Cymraeg.", "en": "English remit."},
    }
    memberships_by_id = {item["id"]: item for item in serialized["memberships"]}
    assert memberships_by_id[membership.id]["extra"]["localised_values"] == {
        "role": {"cy": "Cadeirydd", "en": "Chair"}
    }
    assert memberships_by_id[government_membership.id]["extra"]["localised_values"] == {
        "role": {
            "cy": "Ysgrifennydd y Cabinet dros Enghreifftiau",
            "en": "Cabinet Secretary for Examples",
        }
    }
