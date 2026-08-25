"""Source data models and language configuration for the Senedd scraper."""

from __future__ import annotations

from typing import NamedTuple


class Language(NamedTuple):
    culture: str
    csv_name_column: str
    committee_list_url: str
    website_url: str
    committee_path: str
    current_categories: frozenset[str]

    def committee_url(self, committee_id: str) -> str:
        """Construct the public committee page URL for a ModernGov committee ID."""
        return f"{self.website_url}/{self.committee_path}/{committee_id}"

    def members_csv_url(self, committee_id: str) -> str:
        """Construct the member CSV URL for an internal Umbraco committee ID."""
        return (
            f"{self.website_url}/Umbraco/Api/Committee/"
            f"DownloadCommitteeMembersCsv?committeeId={committee_id}"
            f"&cultureInfo={self.culture}"
        )


ENGLISH = Language(
    culture="en-GB",
    csv_name_column="Name",
    committee_list_url="https://business.senedd.wales/mgwebservice.asmx/GetCommittees",
    website_url="https://senedd.wales",
    committee_path="committee",
    current_categories=frozenset({"Committees", "Business Committee"}),
)
WELSH = Language(
    culture="cy-GB",
    csv_name_column="Enw",
    committee_list_url="https://busnes.senedd.cymru/mgwebservicew.asmx/GetCommittees",
    website_url="https://senedd.cymru",
    committee_path="pwyllgor",
    current_categories=frozenset({"Pwyllgorau", "Y Pwyllgor Busnes"}),
)


class MemberCard(NamedTuple):
    name: str
    role: str | None
    senedd_id: str | None


class CommitteeSummary(NamedTuple):
    modern_gov_id: str
    name: str
    deleted: bool
    expired: bool
    category: str | None


class Committee(NamedTuple):
    id: str
    name: str
    page_url: str
    csv_url: str
    members: list[MemberCard]
    category: str | None = None
    description: str | None = None


class BilingualCommittee(NamedTuple):
    english: Committee
    welsh: Committee


class BilingualMember(NamedTuple):
    person_id: str
    source_person_id: str
    english: MemberCard
    welsh: MemberCard


class BilingualText(NamedTuple):
    cy: str
    en: str


class GovernmentMember(NamedTuple):
    name: str
    role: str
    profile_url: str


class BilingualGovernmentMember(NamedTuple):
    person_id: str
    english: GovernmentMember
    welsh: GovernmentMember
