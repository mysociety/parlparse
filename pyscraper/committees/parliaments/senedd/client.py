"""Assemble bilingual Senedd records from ModernGov and public pages.

ModernGov exposes committee catalogues as XML, while remit text, internal IDs
and current members are spread across rendered pages and linked CSV exports.
Both official languages are paired before the Popolo transform.
"""

from __future__ import annotations

import httpx

from ...config import USER_AGENT
from ...helpers.progress import track
from .models import (
    ENGLISH,
    WELSH,
    BilingualCommittee,
    Committee,
    CommitteeSummary,
    GovernmentMember,
    Language,
)
from .parsing import (
    is_current_committee,
    parse_committee_list,
    parse_committee_page,
    parse_government_members,
    parse_members_csv,
)


class SeneddClient:
    """
    Fetch and combine the English and Welsh Senedd committee sources.
    """

    def __init__(self, timeout: int = 30) -> None:
        """
        Create a client with a shared session and per-request timeout.
        """
        self.client = httpx.Client(
            headers={"User-Agent": USER_AGENT},
            timeout=timeout,
            follow_redirects=True,
        )

    def close(self) -> None:
        """
        Close the shared HTTP connection pool.
        """
        self.client.close()

    def get(self, url: str) -> httpx.Response:
        """
        Fetch a Senedd URL and raise for an unsuccessful HTTP response.
        """
        response = self.client.get(url)
        response.raise_for_status()
        return response

    def committee_list(self, language: Language) -> list[CommitteeSummary]:
        """
        Fetch and parse all committee records for one language.
        """
        response = self.get(language.committee_list_url)
        return parse_committee_list(response.content)

    def committee(self, summary: CommitteeSummary, language: Language) -> Committee:
        """
        Fetch one constructed committee page and its current membership CSV.
        """
        # The page supplies remit text and the internal ID used to construct the
        # CSV endpoint; the CSV is the authoritative current membership list.
        page_url = language.committee_url(summary.modern_gov_id)
        page_response = self.get(page_url)
        committee = parse_committee_page(
            summary, str(page_response.url), page_response.text, language
        )
        members_response = self.get(committee.csv_url)
        members = parse_members_csv(committee, members_response.content, language)
        return Committee(
            id=committee.id,
            name=committee.name,
            page_url=committee.page_url,
            csv_url=committee.csv_url,
            members=members,
            category=committee.category,
            description=committee.description,
        )

    def government_members(self, page_url: str) -> list[GovernmentMember]:
        """Fetch one language's current Welsh Government team."""
        response = self.get(page_url)
        return parse_government_members(response.text, str(response.url))

    def all_committees(self) -> list[BilingualCommittee]:
        """
        Return current committees with their English and Welsh records paired.

        Both list APIs must contain the same current ModernGov IDs. The detail
        pages must then agree on the separate internal committee ID.
        """
        english = {
            item.modern_gov_id: item
            for item in self.committee_list(ENGLISH)
            if is_current_committee(item, ENGLISH)
        }
        welsh = {
            item.modern_gov_id: item
            for item in self.committee_list(WELSH)
            if is_current_committee(item, WELSH)
        }
        if english.keys() != welsh.keys():
            raise ValueError("English and Welsh current committee lists differ")

        committees: list[BilingualCommittee] = []
        internal_ids: set[str] = set()
        for modern_gov_id in track(
            sorted(english, key=int), "Fetching bilingual Senedd committees"
        ):
            english_committee = self.committee(english[modern_gov_id], ENGLISH)
            welsh_committee = self.committee(welsh[modern_gov_id], WELSH)
            if english_committee.id != welsh_committee.id:
                raise ValueError(
                    "English and Welsh pages disagree on internal committee ID: "
                    f"{english_committee.page_url} and {welsh_committee.page_url}"
                )
            if english_committee.id in internal_ids:
                raise ValueError(
                    "The Senedd pages returned duplicate internal ID "
                    f"{english_committee.id}"
                )
            internal_ids.add(english_committee.id)
            committees.append(
                BilingualCommittee(
                    english=english_committee,
                    welsh=welsh_committee,
                )
            )
        return committees
