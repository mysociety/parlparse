"""
Download written questions data from the Scottish Parliament API
and cache it locally.
"""

from __future__ import annotations

import json
from pathlib import Path

import requests
from pydantic import TypeAdapter

from .api_models import SPQuestion

API_URL = "https://data.parliament.scot/api/motionsquestionsanswersquestions"


def download_questions(
    year: int,
    cache_dir: Path,
    force_refresh: bool = False,
) -> list[SPQuestion]:
    """
    Download questions for a given year from the Scottish Parliament API.
    Caches the raw JSON response locally.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"questions_{year}.json"

    if cache_file.exists() and not force_refresh:
        with cache_file.open("r") as f:
            raw_data = json.load(f)
    else:
        response = requests.get(f"{API_URL}?year={year}")
        response.raise_for_status()
        raw_data = response.json()
        with cache_file.open("w") as f:
            json.dump(raw_data, f, indent=2)

    entries = TypeAdapter(list[SPQuestion]).validate_python(raw_data)
    return entries


def get_written_answered_questions(
    year: int,
    cache_dir: Path,
    force_refresh: bool = False,
) -> list[SPQuestion]:
    """
    Download and filter to only written questions that have been answered.
    """
    all_questions = download_questions(year, cache_dir, force_refresh=force_refresh)
    return [q for q in all_questions if q.is_written and q.is_answered]
