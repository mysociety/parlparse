"""Read Westminster history from MNIS and the Committees API.

MNIS supplies dated government, opposition and parliamentary posts in bulk.
Committee history is queried in member batches, while richer metadata requires
one request per current committee and is cached between runs.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from datetime import date
from typing import NamedTuple, Protocol

import httpx

from ...config import USER_AGENT
from ...helpers.progress import track
from .models import CommitteeMembership, CommitteeMetadata, Post
from .parsing import (
    HISTORY_START,
    parse_committee_memberships,
    parse_committee_metadata,
    parse_mnis_posts,
)

MNIS_MEMBERS_URL = (
    "https://data.parliament.uk/membersdataplatform/services/mnis/members/query"
)
COMMITTEE_MEMBERS_URL = "https://committees-api.parliament.uk/api/Members"
COMMITTEE_DETAILS_URL = "https://committees-api.parliament.uk/api/Committees"


class QueryParameter(NamedTuple):
    """One named value sent as an HTTP query parameter."""

    name: str
    value: str


class HttpResponse(Protocol):
    """
    Describe the response features used by the scraper.
    """

    @property
    def content(self) -> bytes:
        """
        Return the raw response body.
        """
        ...

    def json(self) -> object:
        """
        Decode the response body as JSON.
        """
        ...

    def raise_for_status(self) -> object:
        """
        Raise an exception for an unsuccessful response.
        """
        ...


class HttpSession(Protocol):
    """
    Describe the HTTP session operation used by the scraper.
    """

    def close(self) -> None:
        """Close the underlying connection pool."""
        ...

    def get(
        self,
        url: str,
        *,
        timeout: int,
        params: list[QueryParameter] | None,
    ) -> HttpResponse:
        """
        Fetch one response from a URL.
        """
        ...


class HttpxSession:
    """Adapt httpx to the narrower session interface used by the scraper."""

    def __init__(self) -> None:
        self.client = httpx.Client(
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        )

    def close(self) -> None:
        """Close the underlying connection pool."""
        self.client.close()

    def get(
        self,
        url: str,
        *,
        timeout: int,
        params: list[QueryParameter] | None,
    ) -> httpx.Response:
        """Fetch a response after translating named query parameters for httpx."""
        query = httpx.QueryParams()
        for parameter in params or []:
            query = query.add(parameter.name, parameter.value)
        return self.client.get(url, timeout=timeout, params=query)


def batches(items: list[int], batch_size: int) -> Iterator[list[int]]:
    """
    Yield fixed-size batches, rejecting a non-positive batch size.
    """
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1")
    for index in range(0, len(items), batch_size):
        yield items[index : index + batch_size]


class WestminsterClient:
    """
    Fetch bulk role histories from the official Parliament APIs.
    """

    def __init__(
        self,
        timeout: int = 120,
        request_delay: float = 3.0,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        """
        Create a shared, deliberately paced HTTP session.
        """
        if request_delay < 0:
            raise ValueError("request_delay cannot be negative")
        self.timeout = timeout
        self.request_delay = request_delay
        self.sleeper = sleeper
        self.session: HttpSession = HttpxSession()
        self.request_count = 0

    def close(self) -> None:
        """Close the shared HTTP connection pool."""
        self.session.close()

    def get(self, url: str, params: list[QueryParameter] | None = None) -> HttpResponse:
        """
        Fetch a URL, pausing before every request after the first.
        """
        if self.request_count:
            self.sleeper(self.request_delay)
        response = self.session.get(url, timeout=self.timeout, params=params)
        self.request_count += 1
        response.raise_for_status()
        return response

    def posts(self, history_start: date = HISTORY_START) -> list[Post]:
        """
        Fetch all three post-history datasets in one request per house.
        """
        # Commons can be bounded at the 2010 cut-off. Lords uses all members
        # and is trimmed to the same history window during XML parsing.
        output_data = "GovernmentPosts|OppositionPosts|ParliamentaryPosts"
        today = date.today().isoformat()
        queries = (
            f"house=Commons|membership=all|commonsmemberbetween="
            f"{history_start.isoformat()}and{today}",
            "house=Lords|membership=all",
        )
        posts: list[Post] = []
        for query in track(queries, "Fetching Westminster post histories"):
            url = f"{MNIS_MEMBERS_URL}/{query}/{output_data}/"
            posts.extend(parse_mnis_posts(self.get(url).content, history_start))
        return posts

    def committee_details(
        self,
        memberships: list[CommitteeMembership],
        cached_metadata: dict[int, CommitteeMetadata] | None = None,
        full_refresh: bool = False,
    ) -> dict[int, CommitteeMetadata]:
        """
        Add committee purpose details to membership summary metadata.

        A previous output artifact avoids all detail requests for committees it
        contains. New committees are fetched individually. full_refresh ignores
        that cache and fetches every current committee.
        """
        details: dict[int, CommitteeMetadata] = {
            record.committee_id: record.metadata
            or CommitteeMetadata(record.committee_id, record.committee_name)
            for record in memberships
        }
        cached_metadata = cached_metadata or {}
        if not full_refresh:
            for committee_id, metadata in cached_metadata.items():
                details.setdefault(committee_id, metadata)
            for committee_id in details.keys() & cached_metadata.keys():
                current = details[committee_id]
                cached = cached_metadata[committee_id]
                details[committee_id] = current._replace(description=cached.description)

        # Minigroups only cover current committees, so only those need the
        # additional detail request for purpose text. Summary metadata is
        # sufficient to retain links, hierarchy and tags for former committees.
        pending = sorted(
            committee_id
            for committee_id, metadata in details.items()
            if metadata.end_date is None
            and (full_refresh or committee_id not in cached_metadata)
        )
        fetched: set[int] = set()

        def pending_committee_ids() -> Iterator[int]:
            while pending:
                committee_id = pending.pop(0)
                if committee_id not in fetched:
                    yield committee_id

        for committee_id in track(
            pending_committee_ids(), "Fetching Westminster committee details"
        ):
            response = self.get(
                f"{COMMITTEE_DETAILS_URL}/{committee_id}",
                params=[
                    QueryParameter(name="includeBanners", value="false"),
                    QueryParameter(name="showOnWebsiteOnly", value="false"),
                ],
            )
            data = response.json()
            if not isinstance(data, dict):
                raise ValueError(
                    f"The Committees API returned invalid detail for {committee_id}"
                )
            metadata = parse_committee_metadata(data)
            details[committee_id] = metadata
            fetched.add(committee_id)
            if (
                metadata.parent_id
                and metadata.parent_id not in fetched
                and (full_refresh or metadata.parent_id not in cached_metadata)
            ):
                pending.append(metadata.parent_id)
        return details

    def committee_memberships(
        self,
        member_ids: list[int],
        history_start: date = HISTORY_START,
        batch_size: int = 50,
    ) -> list[CommitteeMembership]:
        """
        Fetch all committee histories in multi-member request batches.
        """
        memberships: list[CommitteeMembership] = []
        member_batches = list(batches(sorted(set(member_ids)), batch_size))
        for member_batch in track(
            member_batches, "Fetching Westminster committee histories"
        ):
            params: list[QueryParameter] = [
                QueryParameter(name="Members", value=str(member_id))
                for member_id in member_batch
            ]
            params.extend(
                [
                    QueryParameter(name="MembershipStatus", value="All"),
                    QueryParameter(name="ShowOnWebsiteOnly", value="false"),
                ]
            )
            response = self.get(COMMITTEE_MEMBERS_URL, params=params)
            memberships.extend(
                parse_committee_memberships(response.json(), history_start)
            )
        return memberships
