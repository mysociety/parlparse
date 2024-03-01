"""
Lightweight configuration file loader.
"""

import json
import sys
from functools import lru_cache
from pathlib import Path
from typing import Dict

# if you ares using Python 3.8 or later, you can use the built-in TypedDict
if sys.version_info >= (3, 8):
    from typing import TypedDict
else:
    from typing_extensions import TypedDict


class ConfigDict(TypedDict):
    assembly_domain: str
    default_start_date: str
    public_whip_question_id_prefix: str
    office_map: Dict[str, str]
    name_regex_to_strip: str
    name_corrections: Dict[str, str]
    xml_file_prefix: str


@lru_cache(maxsize=None)
def get_config() -> ConfigDict:
    # Load and parsethe configuration file
    config_path = Path(__file__).parent.parent / "config.json"
    with config_path.open() as config_json_file:
        return json.load(config_json_file)
