import re
from functools import lru_cache
from pathlib import Path
from typing import Optional

from mysoc_validator import Popolo


def nice_name(name: Optional[str]) -> str:
    """
    Convert from pascal case to a nice name.
    This should convert thisIsAName to "This Is A Name"
    """
    if name is None:
        return ""
    split = re.sub(
        """(?x) (  
        [a-z](?=[A-Z]) # lower case that will be followed by uppercase (end of a titled word)  
        |  
        [A-Z](?=[A-Z][a-z]) # upper case followed by uppercase then lowercase (end of an uppercase word)  
    )""",
        r"\1 ",
        name,
    ).strip()

    # capitalise first letter
    return split[0].upper() + split[1:]


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
