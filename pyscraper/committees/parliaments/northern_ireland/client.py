"""Collect Northern Ireland Assembly committee and role datasets.

Current committees are divided across organisation-type endpoints, while roles,
the people catalogue and per-person histories use separate APIs. The public
website supplies committee URLs omitted from the structured feeds.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any

import httpx

from ...config import USER_AGENT
from ...helpers.progress import track
from .models import AssemblyPerson, Committee, MemberRole, NorthernIrelandAssemblyData
from .parsing import (
    ALL_MEMBERS_URL,
    COMMITTEES_INDEX_URL,
    MEMBER_ROLES_URL,
    normalized_committee_name,
    parse_committee_links,
    parse_committees,
    parse_member_roles,
    parse_people,
)

API_ROOT = "https://data.niassembly.gov.uk"
COMMITTEE_URLS = (
    f"{API_ROOT}/organisations.asmx/GetCommitteesListCurrent_AdHoc_JSON",
    f"{API_ROOT}/organisations.asmx/GetCommitteesListCurrent_Other_JSON",
    f"{API_ROOT}/organisations.asmx/GetCommitteesListCurrent_Standing_JSON",
    f"{API_ROOT}/organisations.asmx/GetCommitteesListCurrent_Statutory_JSON",
)
MEMBER_ROLE_HISTORY_URL = (
    f"{API_ROOT}/members.asmx/GetMemberRolesByPersonId_JSON?personId={{person_id}}"
)
MINISTERIAL_ROLE_TYPE = "Ministerial Role"


class NorthernIrelandAssemblyClient:
    """
    Fetch the NI Assembly committee open-data datasets.
    """

    def __init__(self, timeout: int = 30) -> None:
        self.timeout = timeout
        self.session = httpx.Client(
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        )

    def close(self) -> None:
        """Close the shared HTTP connection pool."""
        self.session.close()

    def get_object(self, url: str) -> dict[str, Any]:
        """
        Fetch a JSON object, rejecting unsuccessful or malformed responses.
        """
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError(f"The NI Assembly API did not return an object at {url}")
        return data

    def get_text(self, url: str) -> str:
        """Fetch an official Assembly web page."""
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        return response.text

    def all_data(
        self, committee_links: dict[str, str] | None = None
    ) -> NorthernIrelandAssemblyData:
        """
        Fetch all current committee categories and MLA roles.

        committee_links comes from the previous output artifact. Passing None
        performs a full public-index refresh; an empty mapping is a valid cache
        and does not trigger that extra request.
        """
        committees: list[Committee] = []
        for url in track(COMMITTEE_URLS, "Fetching NI Assembly committee lists"):
            committees.extend(parse_committees(self.get_object(url), url))
        links = (
            parse_committee_links(self.get_text(COMMITTEES_INDEX_URL))
            if committee_links is None
            else committee_links
        )
        committees = [
            committee._replace(
                external_url=links.get(normalized_committee_name(committee.name))
            )
            for committee in committees
        ]
        roles = parse_member_roles(self.get_object(MEMBER_ROLES_URL))
        return NorthernIrelandAssemblyData(committees=committees, roles=roles)

    def all_people(self) -> list[AssemblyPerson]:
        """Fetch all current and former MLAs."""
        return parse_people(self.get_object(ALL_MEMBERS_URL))

    def government_role_history(self, person_ids: set[int]) -> list[MemberRole]:
        """Fetch complete role histories for selected Assembly person IDs.

        There is no bulk history endpoint, so bounded concurrency limits the
        cost of the official per-person service.
        """

        def fetch(person_id: int) -> list[MemberRole]:
            url = MEMBER_ROLE_HISTORY_URL.format(person_id=person_id)
            return parse_member_roles(self.get_object(url), url)

        roles: list[MemberRole] = []
        ordered_person_ids = sorted(person_ids)
        with ThreadPoolExecutor(max_workers=4) as executor:
            histories = executor.map(fetch, ordered_person_ids)
            for person_roles in track(
                histories,
                "Fetching NI ministerial histories",
                total=len(ordered_person_ids),
            ):
                roles.extend(person_roles)
        return [role for role in roles if role.role_type == MINISTERIAL_ROLE_TYPE]
