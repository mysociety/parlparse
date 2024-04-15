"""
Cli for scraping Scottish Parliament 2024

Use `python -m pyscraper.sp_2024 --help` to see available commands
"""

from __future__ import annotations

from .download import fetch_debates_for_dates
from .parse import tidy_up_html
from .convert import convert_xml_to_twfy
import click
from pathlib import Path
import datetime

file_dir = Path(__file__).parent
parldata = Path(file_dir, "..", "..", "..", "parldata")

cache_dir = parldata / "cmpages" / "sp_2024"
output_dir = parldata / "scrapedxml" / "sp_2024"


@click.group()
def cli():
    pass


def cache_dir_iterator(
    cache_dir: Path,
    start_date: datetime.date,
    end_date: datetime.date,
):
    """
    Return an iterator of files in the cache_dir that are between the start and end date
    """

    for file in cache_dir.glob("*.xml"):
        # date is an iso date at the start of the filename
        date = datetime.date.fromisoformat(file.stem[:10])
        if start_date <= date <= end_date:
            yield file


@cli.command()
@click.option(
    "--start-date", help="isodate to start fetching debates from", required=True
)
@click.option("--end-date", help="isodate to end fetching debates at", required=True)
@click.option(
    "--download",
    is_flag=True,
    help="Download the debates, pair with 'override' to redownload all files",
)
@click.option("--parse", is_flag=True, help="Parse the downloaded debates")
@click.option("--convert", is_flag=True, help="Convert the parsed debates")
@click.option("--verbose", is_flag=True, help="Print verbose output")
@click.option("--override", is_flag=True, help="Override existing files")
@click.option(
    "--partial-file-name", help="Only parse/convert files that match this string"
)
def debates(
    start_date: str,
    end_date: str,
    download: bool = False,
    parse: bool = False,
    convert: bool = False,
    verbose: bool = False,
    override: bool = False,
    partial_file_name: str | None = None,
):
    """
    Download transcripts from Scottish Parliament between a start and end date.
    """

    start = datetime.date.fromisoformat(start_date)
    end = datetime.date.fromisoformat(end_date)

    # if none of the flags are set, error that at least one flag must be set
    if not any([download, parse, convert]):
        click.echo("At least one of the flags must be set")
        return

    # iterate through downloaded files if we're downloading them
    # otherwise go find the relevant files based on name
    if download:
        file_iterator = fetch_debates_for_dates(
            start.isoformat(),
            end.isoformat(),
            verbose=verbose,
            cache_dir=cache_dir,
            override=override,
        )
    else:
        file_iterator = cache_dir_iterator(cache_dir, start, end)

    for file in file_iterator:
        if partial_file_name:
            if not file.name.startswith(partial_file_name):
                continue
        if parse:
            if verbose:
                print(f"Parsing up {file}")
            tidy_up_html(file)
        if convert:
            if verbose:
                print(f"Converting {file} to TheyWorkForYou format")
            convert_xml_to_twfy(file, output_dir, verbose=verbose)


if __name__ == "__main__":
    cli(prog_name="python -m pyscraper.sp_2024")
