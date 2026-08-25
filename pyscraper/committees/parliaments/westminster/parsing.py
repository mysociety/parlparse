"""Parse and normalize Westminster post and committee API responses."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Literal, overload

import lxml.etree as etree

from ...helpers.html_text import reduce_purpose_html
from .models import CommitteeMembership, CommitteeMetadata, CommitteeRole, Post

HISTORY_START = date(2010, 5, 6)
POST_TYPES: dict[str, str] = {
    "GovernmentPost": "governmentpost",
    "OppositionPost": "oppositionpost",
    "ParliamentaryPost": "parliamentarypost",
}


@overload
def parse_api_date(
    value: object, field: str, *, optional: Literal[False] = False
) -> date: ...


@overload
def parse_api_date(
    value: object, field: str, *, optional: Literal[True]
) -> date | None: ...


def parse_api_date(value: object, field: str, *, optional: bool = False) -> date | None:
    """
    Parse an ISO timestamp from either Parliament API.
    """
    if value is None or value == "":
        if optional:
            return None
        raise ValueError(f"Missing {field}")
    if not isinstance(value, str):
        raise ValueError(f"Invalid {field}: {value!r}")
    try:
        return datetime.fromisoformat(value).date()
    except ValueError as exc:
        raise ValueError(f"Invalid {field}: {value!r}") from exc


def overlaps_history(end_date: date | None, history_start: date) -> bool:
    """
    Return whether a half-open period reaches the requested history window.
    """
    return end_date is None or end_date > history_start


def element_text(element: etree._Element, name: str) -> str | None:
    """
    Return stripped child text, treating empty XML elements as missing.
    """
    child = element.find(name)
    if child is None or child.text is None:
        return None
    value = child.text.strip()
    return value or None


def parse_mnis_posts(content: bytes, history_start: date = HISTORY_START) -> list[Post]:
    """
    Parse dated post histories from a bulk MNIS Members response.
    """
    xml_parser = etree.XMLParser(resolve_entities=False, no_network=True)
    root = etree.fromstring(content, parser=xml_parser)
    if root.tag != "Members":
        raise ValueError(f"MNIS returned root element {root.tag!r}, not 'Members'")

    posts: list[Post] = []
    for member in root.findall("Member"):
        try:
            member_id = int(member.attrib["Member_Id"])
        except (KeyError, ValueError) as exc:
            raise ValueError(
                "MNIS returned a Member without a numeric Member_Id"
            ) from exc
        for post_type in POST_TYPES:
            container = member.find(f"{post_type}s")
            if container is None:
                continue
            for item in container.findall(post_type):
                try:
                    post_id = int(item.attrib["Id"])
                except (KeyError, ValueError) as exc:
                    raise ValueError(
                        f"MNIS returned a {post_type} without a numeric Id"
                    ) from exc
                start_date = parse_api_date(
                    element_text(item, "StartDate"), "StartDate"
                )
                end_date = parse_api_date(
                    element_text(item, "EndDate"), "EndDate", optional=True
                )
                if not overlaps_history(end_date, history_start):
                    continue
                name = element_text(item, "HansardName") or element_text(item, "Name")
                if not name:
                    raise ValueError(
                        f"MNIS returned {post_type} {post_id} without a name"
                    )
                posts.append(
                    Post(
                        member_id=member_id,
                        post_type=post_type,
                        post_id=post_id,
                        name=name,
                        start_date=start_date,
                        end_date=end_date,
                    )
                )
    return posts


def parse_committee_metadata(data: dict[object, object]) -> CommitteeMetadata:
    """Parse metadata shared by committee summary and detail responses."""
    raw_committee_id = data.get("id")
    if not isinstance(raw_committee_id, (int, str)):
        raise ValueError(f"Committee has invalid ID {raw_committee_id!r}")
    committee_id = int(raw_committee_id)
    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ValueError(f"Committee {committee_id} has no name")

    house = data.get("house")
    if house is not None and (
        not isinstance(house, str) or house not in {"Commons", "Lords", "Joint"}
    ):
        raise ValueError(f"Committee {committee_id} has invalid house {house!r}")

    end_date = parse_api_date(data.get("endDate"), "endDate", optional=True)

    parent = data.get("parentCommittee")
    if parent is not None and not isinstance(parent, dict):
        raise ValueError(f"Committee {committee_id} has an invalid parent")
    try:
        parent_id = int(parent["id"]) if parent else None
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"Committee {committee_id} has an invalid parent ID") from exc

    categories: list[str] = []
    category = data.get("category")
    if category is not None:
        if not isinstance(category, dict) or not isinstance(category.get("name"), str):
            raise ValueError(f"Committee {committee_id} has an invalid category")
        categories.append(category["name"].strip())

    committee_types = data.get("committeeTypes", [])
    if committee_types is None:
        committee_types = []
    if not isinstance(committee_types, list):
        raise ValueError(f"Committee {committee_id} has invalid committee types")
    for committee_type in committee_types:
        if not isinstance(committee_type, dict) or not isinstance(
            committee_type.get("name"), str
        ):
            raise ValueError(f"Committee {committee_id} has an invalid committee type")
        categories.append(committee_type["name"].strip())

    purpose = data.get("purpose")
    if purpose is not None and not isinstance(purpose, str):
        raise ValueError(f"Committee {committee_id} has an invalid purpose")
    description = reduce_purpose_html(purpose) if purpose else None

    return CommitteeMetadata(
        id=committee_id,
        name=name.strip(),
        house=house,
        end_date=end_date,
        parent_id=parent_id,
        # Preserve the API's category order for deterministic generated output.
        categories=tuple(dict.fromkeys(item for item in categories if item)),
        description=description or None,
        external_url=f"https://committees.parliament.uk/committee/{committee_id}/",
    )


def parse_committee_memberships(
    data: object, history_start: date = HISTORY_START
) -> list[CommitteeMembership]:
    """
    Parse historical memberships returned by the Committees API.
    """
    if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
        raise ValueError("The Committees API did not return a list of members")

    memberships: list[CommitteeMembership] = []
    for member in data:
        member_info = member.get("memberInfo")
        if isinstance(member_info, dict) and member_info.get("mnisId") is not None:
            member_id = int(member_info["mnisId"])
        else:
            member_id = int(member["id"])
        committees = member.get("committees", [])
        if not isinstance(committees, list):
            raise ValueError(f"Invalid committees list for member {member_id}")
        for committee in committees:
            if not isinstance(committee, dict):
                raise ValueError(f"Invalid committee for member {member_id}")
            metadata = parse_committee_metadata(committee)
            committee_id = metadata.id
            committee_name = metadata.name
            raw_roles = committee.get("roles", [])
            if not isinstance(raw_roles, list):
                raise ValueError(
                    f"Invalid roles for member {member_id}, committee {committee_id}"
                )
            roles: list[CommitteeRole] = []
            for raw_role in raw_roles:
                if not isinstance(raw_role, dict):
                    raise ValueError(
                        f"Invalid role for member {member_id}, committee {committee_id}"
                    )
                details = raw_role.get("role")
                if not isinstance(details, dict):
                    raise ValueError(
                        f"Missing role details for member {member_id}, "
                        f"committee {committee_id}"
                    )
                start_date = parse_api_date(raw_role.get("startDate"), "startDate")
                end_date = parse_api_date(
                    raw_role.get("endDate"), "endDate", optional=True
                )
                if not overlaps_history(end_date, history_start):
                    continue
                role_name = details.get("name")
                if role_name is not None and not isinstance(role_name, str):
                    raise ValueError(
                        f"Invalid role name for member {member_id}, "
                        f"committee {committee_id}"
                    )
                roles.append(
                    CommitteeRole(
                        name=role_name.strip() if role_name else None,
                        is_chair=bool(details.get("isChair")),
                        start_date=start_date,
                        end_date=end_date,
                    )
                )
            if roles:
                memberships.append(
                    CommitteeMembership(
                        member_id=member_id,
                        committee_id=committee_id,
                        committee_name=committee_name,
                        roles=roles,
                        metadata=metadata,
                    )
                )
    return memberships


def normalized_committee_roles(roles: list[CommitteeRole]) -> list[CommitteeRole]:
    """
    Create a non-overlapping role timeline, with chair roles taking priority.
    """
    if not roles:
        return []
    boundaries = sorted(
        {role.start_date for role in roles}
        | {role.end_date for role in roles if role.end_date is not None}
    )
    periods: list[CommitteeRole] = []
    for index, start_date in enumerate(boundaries):
        active = [
            role
            for role in roles
            if role.start_date <= start_date
            and (role.end_date is None or start_date < role.end_date)
        ]
        if not active:
            continue
        chairs = [role for role in active if role.is_chair]
        named = [
            role
            for role in active
            if role.name and role.name.casefold() != "member" and not role.is_chair
        ]
        selected = chairs[0] if chairs else named[0] if named else active[0]
        role_name = "Chair" if chairs else selected.name
        if role_name and role_name.casefold() == "member":
            role_name = None
        end_date = boundaries[index + 1] if index + 1 < len(boundaries) else None
        if end_date is None and not any(role.end_date is None for role in active):
            continue
        period = CommitteeRole(
            name=role_name,
            is_chair=bool(chairs),
            start_date=start_date,
            end_date=end_date,
        )
        if (
            periods
            and periods[-1].name == period.name
            and periods[-1].end_date == period.start_date
        ):
            previous = periods[-1]
            periods[-1] = CommitteeRole(
                name=previous.name,
                is_chair=previous.is_chair,
                start_date=previous.start_date,
                end_date=period.end_date,
            )
        else:
            periods.append(period)
    return periods


def slugify(value: str) -> str:
    """
    Return the legacy parlparse organization slug for a display name.
    """
    return re.sub(r"[^\w ]", "", value).replace(" ", "-").lower()


def committee_organization_name(name: str) -> str:
    """
    Apply the committee suffix rule used by the existing generator.
    """
    if re.search(r"panel|committee|commission|court", name, flags=re.IGNORECASE):
        return name
    return f"{name} Committee"
