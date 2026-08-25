from unittest.mock import Mock

import httpx
import pytest

from pyscraper.committees.helpers.http import HttpClient


def test_invalid_json_reports_response_context() -> None:
    """A maintenance page should identify its URL, type, and response prefix."""
    client = HttpClient()
    response = httpx.Response(
        200,
        headers={"content-type": "text/html"},
        text="<html> Service unavailable </html>",
        request=httpx.Request("GET", "https://example.test/api"),
    )
    client.get = Mock(return_value=response)  # type: ignore[method-assign]

    with pytest.raises(ValueError) as error:
        client.get_json("https://example.test/api")

    message = str(error.value)
    assert "https://example.test/api" in message
    assert "text/html" in message
    assert "Service unavailable" in message
    client.close()
