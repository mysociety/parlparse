"""Collect the Scottish Parliament datasets used by the Popolo transform.

The open-data service publishes committees, role definitions, assignments and
people as separate whole-table JSON feeds. Public committee URLs are absent
from those feeds, so they are supplemented from the parliamentary website index
or from the preceding output when that index is unchanged.
"""

from __future__ import annotations

import httpx
from pydantic import TypeAdapter

from ...config import USER_AGENT
from ...helpers.progress import track
from .models import (
    Committee,
    CommitteeData,
    CommitteeRole,
    GovernmentRole,
    MemberGovernmentRole,
    PersonCommitteeRole,
    ScottishPerson,
)
from .parsing import COMMITTEE_INDEX_URL, parse_committee_links

API_ROOT = "https://data.parliament.scot/api"
COMMITTEES_URL = f"{API_ROOT}/committees/json"
COMMITTEE_ROLES_URL = f"{API_ROOT}/committeeroles/json"
PERSON_COMMITTEE_ROLES_URL = f"{API_ROOT}/personcommitteeroles/json"
GOVERNMENT_ROLES_URL = f"{API_ROOT}/governmentroles/json"
MEMBER_GOVERNMENT_ROLES_URL = f"{API_ROOT}/membergovernmentroles/json"
MEMBERS_URL = f"{API_ROOT}/members/json"


class ScottishParliamentClient:
    """
    Fetch the Scottish Parliament committee open-data datasets.
    """

    def __init__(self, timeout: int = 30) -> None:
        """
        Create a client with a shared session and per-request timeout.
        """
        self.timeout = timeout
        self.session = httpx.Client(
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        )

    def close(self) -> None:
        """Close the shared HTTP connection pool."""
        self.session.close()

    def get_json(self, url: str) -> object:
        """
        Fetch JSON from an API URL and reject unsuccessful responses.
        """
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        data: object = response.json()
        return data

    def get_text(self, url: str) -> str:
        """Fetch text from a public Scottish Parliament page."""
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        return response.text

    def get_data(self, committee_links: dict[str, str] | None = None) -> CommitteeData:
        """
        Fetch and validate all datasets needed for committee membership.

        committee_links comes from the previous output artifact. Passing None
        performs a full public-index refresh; an empty mapping is a valid cache
        and does not trigger that extra request.
        """
        urls = (
            COMMITTEES_URL,
            COMMITTEE_ROLES_URL,
            PERSON_COMMITTEE_ROLES_URL,
            GOVERNMENT_ROLES_URL,
            MEMBER_GOVERNMENT_ROLES_URL,
            MEMBERS_URL,
        )
        raw = {
            url: self.get_json(url)
            for url in track(urls, "Fetching Scottish Parliament datasets")
        }
        committees = TypeAdapter(list[Committee]).validate_python(raw[COMMITTEES_URL])
        roles = TypeAdapter(list[CommitteeRole]).validate_python(
            raw[COMMITTEE_ROLES_URL]
        )
        person_roles = TypeAdapter(list[PersonCommitteeRole]).validate_python(
            raw[PERSON_COMMITTEE_ROLES_URL]
        )
        government_roles = TypeAdapter(list[GovernmentRole]).validate_python(
            raw[GOVERNMENT_ROLES_URL]
        )
        member_government_roles = TypeAdapter(
            list[MemberGovernmentRole]
        ).validate_python(raw[MEMBER_GOVERNMENT_ROLES_URL])
        members = TypeAdapter(list[ScottishPerson]).validate_python(raw[MEMBERS_URL])
        return CommitteeData(
            committees=committees,
            roles=roles,
            person_roles=person_roles,
            government_roles=government_roles,
            member_government_roles=member_government_roles,
            members=members,
            committee_links=(
                parse_committee_links(self.get_text(COMMITTEE_INDEX_URL))
                if committee_links is None
                else committee_links
            ),
        )
