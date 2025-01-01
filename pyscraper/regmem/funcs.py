from functools import lru_cache
from pathlib import Path

from mysoc_validator import Popolo


def get_higher_path(folder_name: str) -> Path:
    current_level = Path.cwd()
    allowed_levels = 3
    for i in range(allowed_levels):
        if (current_level / folder_name).exists():
            return current_level / folder_name
        current_level = current_level.parent
    return Path.home() / folder_name


parldata_path = get_higher_path("parldata")
memberdata_path = get_higher_path("members")


@lru_cache
def get_popolo() -> Popolo:
    return Popolo.from_path(memberdata_path / "people.json")
