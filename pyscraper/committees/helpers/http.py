"""Shared HTTP transport for committee source scrapers."""

from __future__ import annotations

import time
from collections.abc import Callable

import httpx

from ..config import USER_AGENT


class HttpClient:
    """Fetch checked responses through one shared connection pool."""

    def __init__(self, timeout: int = 30) -> None:
        self.timeout = timeout
        self.session = httpx.Client(
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        )

    def close(self) -> None:
        """Close the underlying connection pool."""
        self.session.close()

    def get(
        self,
        url: str,
        params: httpx.QueryParamTypes | None = None,
    ) -> httpx.Response:
        """Fetch a successful response."""
        response = self.session.get(url, timeout=self.timeout, params=params)
        response.raise_for_status()
        return response

    def get_json(
        self,
        url: str,
        params: httpx.QueryParamTypes | None = None,
    ) -> object:
        """Fetch JSON, adding response context when decoding fails."""
        response = self.get(url, params=params)
        try:
            return response.json()
        except ValueError as exc:
            content_type = response.headers.get("content-type", "unknown")
            preview = " ".join(response.text[:200].split())
            raise ValueError(
                f"Invalid JSON from {response.url} "
                f"(content-type {content_type!r}; response starts {preview!r})"
            ) from exc

    def get_text(self, url: str) -> str:
        """Fetch a text response."""
        return self.get(url).text


class PacedHttpClient(HttpClient):
    """Delay successive requests to avoid overloading sensitive APIs."""

    def __init__(
        self,
        timeout: int = 120,
        request_delay: float = 3.0,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        if request_delay < 0:
            raise ValueError("request_delay cannot be negative")
        super().__init__(timeout=timeout)
        self.request_delay = request_delay
        self.sleeper = sleeper
        self.request_count = 0

    def get(
        self,
        url: str,
        params: httpx.QueryParamTypes | None = None,
    ) -> httpx.Response:
        """Fetch a response, pausing before every request after the first."""
        if self.request_count:
            self.sleeper(self.request_delay)
        response = super().get(url, params=params)
        self.request_count += 1
        return response
