import re
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Optional

from mysoc_validator import Popolo
from pydantic import BaseModel, RootModel


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


class RegmemIndexEntry(BaseModel):
    date: date
    path: str
    is_latest: bool = False


class RegmemIndex(RootModel[dict[str, list[RegmemIndexEntry]]]):
    pass


def write_regmem_index() -> Path:
    """
    Build an index.json of all stored universal regmem registers, grouped by chamber.

    The format is:
    {
      "commons": [{"date": "YYYY-MM-DD", "path": "commons/file.json", "is_latest": true}],
      ...
    }
    """
    base_folder = parldata_path / "scrapedjson" / "universal_format_regmem"
    base_folder.mkdir(parents=True, exist_ok=True)

    index = RegmemIndex(root={})

    for chamber_folder in sorted(x for x in base_folder.iterdir() if x.is_dir()):
        chamber_name = chamber_folder.name
        entries: list[RegmemIndexEntry] = []

        for json_file in sorted(chamber_folder.rglob("*.json")):
            match = re.search(r"(\d{4}-\d{2}-\d{2})", json_file.name)
            if not match:
                continue
            register_date = date.fromisoformat(match.group(1))
            entries.append(
                RegmemIndexEntry(
                    date=register_date,
                    path=json_file.relative_to(base_folder).as_posix(),
                )
            )

        entries.sort(key=lambda x: x.date)

        if entries:
            latest_date = entries[-1].date
            for entry in entries:
                entry.is_latest = entry.date == latest_date

        index.root[chamber_name] = entries

    index_path = base_folder / "index.json"

    with index_path.open("w") as f:
        f.write(index.model_dump_json(indent=2))

    return index_path
