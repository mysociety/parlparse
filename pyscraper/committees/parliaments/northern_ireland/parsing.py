"""Parse Northern Ireland Assembly committee source responses."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from .models import AssemblyPerson, Committee, MemberRole


def nested_records(
    data: dict[str, Any], container_key: str, records_key: str, source: str
) -> list[dict[str, Any]]:
    """
    Extract a list of records from the nested objects returned by the API.
    """
    container = data.get(container_key)
    if not isinstance(container, dict):
        raise ValueError(f"Invalid {container_key} object returned by {source}")
    records = container.get(records_key, [])
    if isinstance(records, dict):
        records = [records]
    if not isinstance(records, list) or not all(
        isinstance(record, dict) for record in records
    ):
        raise ValueError(f"Invalid {records_key} list returned by {source}")
    return records


def parse_committees(data: dict[str, Any], source: str) -> list[Committee]:
    """
    Parse one of the Assembly's current-committee responses.
    """
    committees: list[Committee] = []
    records = nested_records(data, "OrganisationsList", "Organisation", source)
    for index, item in enumerate(records):
        try:
            committees.append(
                Committee(
                    id=int(item["OrganisationId"]),
                    name=str(item["OrganisationName"]).strip(),
                    committee_type=str(item["OrganisationType"]).strip(),
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(
                f"Invalid NI committee record {index} from {source}: {exc}"
            ) from exc
    return committees


def parse_people(
    data: dict[str, Any], source: str = "NI Assembly members API"
) -> list[AssemblyPerson]:
    """Parse current and former MLAs from the Assembly members API."""
    people: list[AssemblyPerson] = []
    records = nested_records(data, "AllMembersList", "Member", source)
    for index, item in enumerate(records):
        try:
            people.append(
                AssemblyPerson(
                    person_id=int(item["PersonId"]),
                    name=" ".join(
                        part
                        for part in (
                            str(item.get("MemberFirstName", "")).strip(),
                            str(item.get("MemberLastName", "")).strip(),
                        )
                        if part
                    ),
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(
                f"Invalid NI person record {index} from {source}: {exc}"
            ) from exc
    return people


def normalized_committee_name(value: str) -> str:
    """Normalize API names, link labels and URL slugs for matching."""
    words = re.sub(r"[^a-z0-9]+", " ", value.casefold()).split()
    ignored = {"committee", "for", "on", "the"}
    return " ".join(word for word in words if word not in ignored)


def parse_committee_links(html: str, index_url: str) -> dict[str, str]:
    """Return normalized current-mandate committee links from the index."""
    soup = BeautifulSoup(html, "html.parser")
    links: dict[str, str] = {}
    mandate_prefix = "/assembly-business/committees/2022-2027/"
    for anchor in soup.select("a[href]"):
        href = anchor.get("href")
        if not isinstance(href, str):
            continue
        absolute_url = urljoin(index_url, href)
        path = urlparse(absolute_url).path
        if not path.startswith(mandate_prefix):
            continue
        remainder = path[len(mandate_prefix) :].strip("/")
        if not remainder or "/" in remainder:
            continue
        names = [" ".join(anchor.stripped_strings), remainder.replace("-", " ")]
        for name in names:
            normalized = normalized_committee_name(name)
            if normalized:
                links[normalized] = absolute_url
    return links


def api_date(value: object) -> str | None:
    """Convert an NI Assembly API timestamp to a Popolo date."""
    if value in (None, ""):
        return None
    return datetime.fromisoformat(str(value)).date().isoformat()


def parse_member_roles(
    data: dict[str, Any], source: str = "NI Assembly member roles API"
) -> list[MemberRole]:
    """
    Parse current or historical roles held by MLAs.
    """
    roles: list[MemberRole] = []
    records = nested_records(data, "AllMembersRoles", "Role", source)
    for index, item in enumerate(records):
        try:
            roles.append(
                MemberRole(
                    affiliation_id=int(item["AffiliationId"]),
                    person_id=int(item["PersonId"]),
                    role_type=str(item["RoleType"]).strip(),
                    role=str(item["Role"]).strip(),
                    committee_id=int(item["OrganisationId"]),
                    organization_name=str(item.get("Organisation", "")).strip(),
                    affiliation_title=(
                        str(item["AffiliationTitle"]).strip()
                        if item.get("AffiliationTitle")
                        else None
                    ),
                    start_date=api_date(item.get("AffiliationStart")),
                    end_date=api_date(item.get("AffiliationEnd")),
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(
                f"Invalid NI member-role record {index} from {source}: {exc}"
            ) from exc
    return roles
