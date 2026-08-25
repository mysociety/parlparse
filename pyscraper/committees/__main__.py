"""
Run committee and parliamentary post scrapers.
"""

from typer import Typer

from .helpers.progress import progress_output

app = Typer(pretty_exceptions_enable=False)


@app.command(name="uk-committees")
def uk_committees(quiet: bool = False) -> None:
    """
    Fetch current UK Parliament committee information and write group JSON files.
    """
    from .legacy.uk_committees.scraper import (
        convert_to_groups,
        get_committee_all_items,
    )

    with progress_output(not quiet):
        get_committee_all_items()
        convert_to_groups()


if __name__ == "__main__":
    app()
