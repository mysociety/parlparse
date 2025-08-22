"""
CLI to download committee information from Parliament APIs and convert to a common group shorthand.
"""

from typer import Typer

from .commons_api import VerboseSettings
from .commons_api import (
    convert_to_groups as uk_convert_to_groups,
)
from .commons_api import (
    get_committee_all_items as uk_get_committee_all_items,
)

app = Typer()


@app.command(name="all")
def all_chambers(quiet: bool = False):
    """
    Fetch all committees from all parliaments (uk-only currently)
    """
    VerboseSettings.verbose = not quiet
    uk_get_committee_all_items()
    uk_convert_to_groups()


@app.command(name="parliament")
def parliament(slug: str = "uk", quiet: bool = False):
    """
    Fetch all committees from a specific parliament (UK parl only supported at moment)
    """
    VerboseSettings.verbose = not quiet
    uk_get_committee_all_items()
    uk_convert_to_groups()


if __name__ == "__main__":
    app()
