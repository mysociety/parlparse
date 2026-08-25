"""Parse and normalize Senedd committee and government responses."""

from __future__ import annotations

import csv
import io
import re
from urllib.parse import parse_qs, urljoin, urlparse
from xml.etree import ElementTree

from bs4 import BeautifulSoup
from bs4.element import Tag

from .models import (
    ENGLISH,
    Committee,
    CommitteeSummary,
    GovernmentMember,
    Language,
    MemberCard,
)


def normalize_member_name(name: str) -> str:
    """
    Return a member name without the Senedd's English or Welsh suffix.
    """
    return re.sub(r"\s+(?:AS|MS)$", "", name.strip(), flags=re.IGNORECASE)


def senedd_id_from_card(card: Tag) -> str | None:
    """
    Extract the numeric Senedd member ID from a profile card's image URL.

    Return ``None`` when the card has no recognized member image URL.
    """
    image = card.select_one("img[data-src], img[src]")
    image_value = (image.get("data-src") or image.get("src")) if image else None
    image_url = image_value if isinstance(image_value, str) else None
    match = re.search(r"/Info0*(\d+)/", image_url or "", flags=re.IGNORECASE)
    return match.group(1) if match else None


def parse_member_cards(soup: BeautifulSoup) -> dict[str, MemberCard]:
    """
    Extract the members, roles and Senedd IDs displayed on a committee page.

    The returned mapping is keyed by normalized member name so it can be
    matched against the committee members CSV.
    """
    members: dict[str, MemberCard] = {}
    for card in soup.select(".person-search-result-item"):
        fields = card.select(".person-search-result-item__text")
        if not fields:
            continue
        name = " ".join(fields[0].stripped_strings)
        role_tag = next(
            (field for field in fields[1:] if "-bold" in field.get("class", [])),
            None,
        )
        role = " ".join(role_tag.stripped_strings) if role_tag else None
        members[normalize_member_name(name)] = MemberCard(
            name=name, role=role or None, senedd_id=senedd_id_from_card(card)
        )
    return members


def parse_government_members(html: str, page_url: str) -> list[GovernmentMember]:
    """Parse the current minister cards from a Welsh Government page."""
    soup = BeautifulSoup(html, "html.parser")
    members: list[GovernmentMember] = []
    for card in soup.select(".key-person"):
        anchor = card.select_one("a[href]")
        name_tag = card.select_one(".key-person__details > span")
        role_tag = card.select_one(".key-person__details .subtitle")
        if anchor is None or name_tag is None or role_tag is None:
            continue
        href = anchor.get("href")
        if not isinstance(href, str):
            continue
        name = " ".join(name_tag.stripped_strings)
        role = " ".join(role_tag.stripped_strings)
        if name and role:
            members.append(GovernmentMember(name, role, urljoin(page_url, href)))
    if not members:
        raise ValueError(f"No Welsh Government ministers found on {page_url}")
    return members


def government_member_name(value: str) -> str:
    """Normalize a Welsh Government card name for matching to people.json."""
    name = normalize_member_name(value)
    return re.sub(
        r"^(?:(?:The )?Rt Hon|Y Gwir Anrh(?:ydeddus)?)\s+",
        "",
        name,
        flags=re.IGNORECASE,
    )


def parse_committee_list(content: bytes) -> list[CommitteeSummary]:
    """
    Parse the ModernGov committee list returned by either language service.

    Missing fields, invalid boolean values, duplicate IDs or disagreement with
    the declared result count raise ``ValueError``.
    """
    try:
        root = ElementTree.fromstring(content)
    except ElementTree.ParseError as exc:
        raise ValueError("The Senedd committee list is not valid XML") from exc

    summaries: list[CommitteeSummary] = []
    committee_ids: set[str] = set()
    for item in root.findall("committee"):
        committee_id = (item.findtext("committeeid") or "").strip()
        name = (item.findtext("committeetitle") or "").strip()
        deleted_text = (item.findtext("committeedeleted") or "").strip()
        expired_text = (item.findtext("committeeexpired") or "").strip()
        category = (item.findtext("committeecategory") or "").strip() or None
        if not committee_id or not name:
            raise ValueError("A Senedd committee is missing its ID or title")
        if deleted_text not in {"True", "False"}:
            raise ValueError(f"Committee {committee_id} has an invalid deleted flag")
        if expired_text not in {"True", "False"}:
            raise ValueError(f"Committee {committee_id} has an invalid expired flag")
        if committee_id in committee_ids:
            raise ValueError(f"The Senedd API returned duplicate ID {committee_id}")
        committee_ids.add(committee_id)
        summaries.append(
            CommitteeSummary(
                modern_gov_id=committee_id,
                name=name,
                deleted=deleted_text == "True",
                expired=expired_text == "True",
                category=category,
            )
        )

    count_text = (root.findtext("committeescount") or "").strip()
    if not count_text.isdigit() or int(count_text) != len(summaries):
        raise ValueError("The Senedd committee count does not match its records")
    return summaries


def is_current_committee(summary: CommitteeSummary, language: Language) -> bool:
    """
    Return whether a list record represents a current Senedd committee.
    """
    return (
        not summary.deleted
        and not summary.expired
        and summary.category in language.current_categories
    )


def parse_committee_page(
    summary: CommitteeSummary,
    page_url: str,
    html: str,
    language: Language,
) -> Committee:
    """
    Parse member metadata and the internal committee ID from a committee page.

    Names come from the language-specific list API. The page is retained as a
    source for member roles, stable Senedd member IDs and the separate internal
    ID required by the CSV endpoint. Missing or ambiguous IDs raise
    ``ValueError``.
    """
    soup = BeautifulSoup(html, "html.parser")
    csv_link = soup.select_one('a[href*="DownloadCommitteeMembersCsv"]')
    if not csv_link:
        raise ValueError(f"No committee members CSV link found on {page_url}")
    csv_link_url = csv_link.get("href")
    if not isinstance(csv_link_url, str):
        raise ValueError(f"No valid committee members CSV link found on {page_url}")
    ids = parse_qs(urlparse(csv_link_url).query).get("committeeId", [])
    if len(ids) != 1:
        raise ValueError(f"No unique internal committee ID found on {page_url}")
    committee_id = ids[0]
    description = section_text(soup, "Remit" if language is ENGLISH else "Cylch Gwaith")
    return Committee(
        id=committee_id,
        name=summary.name,
        page_url=page_url,
        csv_url=language.members_csv_url(committee_id),
        members=list(parse_member_cards(soup).values()),
        category=summary.category,
        description=description,
    )


def section_text(soup: BeautifulSoup, heading_text: str) -> str | None:
    """Extract paragraph text belonging to a named h2 section."""
    heading = next(
        (
            item
            for item in soup.find_all("h2")
            if " ".join(item.stripped_strings).casefold() == heading_text.casefold()
        ),
        None,
    )
    if heading is None:
        return None
    paragraphs: list[str] = []
    for item in heading.find_all_next(["h2", "p"]):
        if item.name == "h2":
            break
        text = " ".join(item.stripped_strings)
        if text:
            paragraphs.append(text)
    return "\n\n".join(paragraphs) or None


def parse_members_csv(
    committee: Committee, content: bytes, language: Language
) -> list[MemberCard]:
    """
    Select current committee members using the Senedd members CSV.

    The CSV is authoritative for current membership, while the matching page
    cards provide each member's committee role and stable Senedd identifier.
    A CSV name without a corresponding page card raises ``ValueError``.
    """
    page_members = {
        normalize_member_name(member.name): member for member in committee.members
    }
    members: list[MemberCard] = []
    for row in csv.DictReader(io.StringIO(content.decode("utf-8-sig"))):
        raw_name = row.get(language.csv_name_column)
        if not raw_name:
            raise ValueError(
                f"Missing {language.csv_name_column!r} in {committee.csv_url}"
            )
        name = normalize_member_name(raw_name)
        page_member = page_members.get(name)
        if not page_member:
            raise ValueError(
                f"API member {raw_name!r} was not found on {committee.page_url}"
            )
        members.append(MemberCard(name, page_member.role, page_member.senedd_id))
    return members
