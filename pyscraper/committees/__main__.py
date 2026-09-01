"""
Run committee and parliamentary post scrapers.
"""

from pathlib import Path

from typer import Typer

from .config import REPO_ROOT
from .helpers.progress import set_verbose

app = Typer(pretty_exceptions_enable=False)
DEFAULT_PEOPLE_PATH = REPO_ROOT / "members" / "people.json"
POSTS_PATH = REPO_ROOT / "members" / "posts"
NI_ASSEMBLY_DEFAULT_OUTPUT_PATH = POSTS_PATH / "ni-assembly-committees.json"
SCOTTISH_PARLIAMENT_DEFAULT_OUTPUT_PATH = (
    POSTS_PATH / "scottish-parliament-committees.json"
)
SENEDD_DEFAULT_OUTPUT_PATH = POSTS_PATH / "senedd-committees.json"
WESTMINSTER_DEFAULT_OUTPUT_PATH = POSTS_PATH / "westminster-parliament-posts.json"


@app.command(name="uk-committees")
def uk_committees(quiet: bool = False) -> None:
    """
    Fetch current UK Parliament committee information and write group JSON files.
    """
    from .legacy.uk_committees.scraper import (
        convert_to_groups,
        get_committee_all_items,
    )

    with set_verbose(not quiet):
        get_committee_all_items()
        convert_to_groups()


@app.command(name="senedd")
def senedd(
    output_path: Path = SENEDD_DEFAULT_OUTPUT_PATH,
    people_path: Path = DEFAULT_PEOPLE_PATH,
    quiet: bool = False,
) -> None:
    """
    Write current Senedd committees and government posts in bilingual Popolo.
    """
    from .parliaments.senedd.scraper import scrape_senedd_committees

    with set_verbose(not quiet):
        scrape_senedd_committees(
            output_path=output_path,
            people_path=people_path,
        )


@app.command(name="scotland")
def scotland(
    output_path: Path = SCOTTISH_PARLIAMENT_DEFAULT_OUTPUT_PATH,
    people_path: Path = DEFAULT_PEOPLE_PATH,
    full_refresh: bool = False,
    quiet: bool = False,
) -> None:
    """
    Write Scottish committee memberships and government post history in Popolo.
    """
    from .parliaments.scotland.scraper import (
        scrape_scottish_parliament_committees,
    )

    with set_verbose(not quiet):
        scrape_scottish_parliament_committees(
            output_path=output_path,
            people_path=people_path,
            full_refresh=full_refresh,
        )


@app.command(name="northern-ireland")
def northern_ireland(
    output_path: Path = NI_ASSEMBLY_DEFAULT_OUTPUT_PATH,
    people_path: Path = DEFAULT_PEOPLE_PATH,
    full_refresh: bool = False,
    quiet: bool = False,
) -> None:
    """
    Write NI committee memberships and ministerial post history in Popolo.
    """
    from .parliaments.northern_ireland.scraper import (
        scrape_ni_assembly_committees,
    )

    with set_verbose(not quiet):
        scrape_ni_assembly_committees(
            output_path=output_path,
            people_path=people_path,
            full_refresh=full_refresh,
        )


@app.command(name="westminster")
def westminster(
    output_path: Path = WESTMINSTER_DEFAULT_OUTPUT_PATH,
    people_path: Path = DEFAULT_PEOPLE_PATH,
    request_delay: float = 3.0,
    batch_size: int = 50,
    full_refresh: bool = False,
    quiet: bool = False,
) -> None:
    """
    Write Westminster role histories from the 2010 general election onward.
    """
    from .parliaments.westminster.scraper import scrape_westminster_roles

    with set_verbose(not quiet):
        scrape_westminster_roles(
            output_path=output_path,
            people_path=people_path,
            request_delay=request_delay,
            batch_size=batch_size,
            full_refresh=full_refresh,
        )


if __name__ == "__main__":
    app()
