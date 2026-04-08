"""
CLI for downloading and converting Scottish Parliament written questions.

Use `python -m pyscraper.sp_wrans --help` to see available commands.
"""

from __future__ import annotations

import datetime

import typer

from pyscraper.regmem.funcs import parldata_path

from .convert import convert_questions_to_xml
from .download import get_written_answered_questions

cache_dir = parldata_path / "cmpages" / "sp_wrans"
output_dir = parldata_path / "scrapedxml" / "sp-written"

FIRST_YEAR = 2011

app = typer.Typer()


def _convert_year(year: int, force_refresh: bool = False, verbose: bool = False) -> int:
    """Convert a single year's questions. Returns number of XML files written."""
    if verbose:
        print(f"Fetching written answered questions for {year}...")

    questions = get_written_answered_questions(
        year=year,
        cache_dir=cache_dir,
        force_refresh=force_refresh,
    )

    if verbose:
        print(f"Found {len(questions)} answered written questions for {year}")

    paths = convert_questions_to_xml(
        questions=questions,
        output_dir=output_dir,
        verbose=verbose,
    )

    if verbose:
        print(f"Wrote {len(paths)} XML files for {year}")

    return len(paths)


def _convert_date_range(
    start_date: datetime.date,
    end_date: datetime.date,
    force_refresh: bool = False,
    verbose: bool = False,
) -> int:
    """
    Convert questions in a date range. Returns number of XML files written.
    """
    # Determine which years to fetch (start year to end year inclusive)
    start_year = start_date.year
    end_year = end_date.year

    all_questions = []

    for year in range(start_year, end_year + 1):
        if verbose:
            print(f"Fetching written answered questions for {year}...")

        year_questions = get_written_answered_questions(
            year=year,
            cache_dir=cache_dir,
            force_refresh=force_refresh,
        )
        all_questions.extend(year_questions)

    # Filter questions by answer date within the specified range
    filtered_questions = [
        q
        for q in all_questions
        if q.answer_date_only and start_date <= q.answer_date_only <= end_date
    ]

    if verbose:
        print(
            f"Found {len(filtered_questions)} answered written questions "
            f"between {start_date} and {end_date}"
        )

    paths = convert_questions_to_xml(
        questions=filtered_questions,
        output_dir=output_dir,
        verbose=verbose,
    )

    if verbose:
        print(f"Wrote {len(paths)} XML files for date range")

    return len(paths)


@app.command()
def convert(
    year: int = typer.Option(2026, help="Year to fetch questions for"),
    force_refresh: bool = typer.Option(False, help="Re-download cached data"),
    verbose: bool = typer.Option(False, help="Print verbose output"),
):
    """
    Download written questions for a single year and convert to TWFY XML.
    """
    _convert_year(year, force_refresh=force_refresh, verbose=verbose)


@app.command()
def convert_all(
    force_refresh: bool = typer.Option(False, help="Re-download cached data"),
    verbose: bool = typer.Option(False, help="Print verbose output"),
):
    """
    Download and convert written questions for all years (2011 to current).
    """
    current_year = datetime.date.today().year
    total_files = 0
    for year in range(FIRST_YEAR, current_year + 1):
        total_files += _convert_year(year, force_refresh=force_refresh, verbose=verbose)

    if verbose:
        print(
            f"Done. Wrote {total_files} XML files across "
            f"{current_year - FIRST_YEAR + 1} years to {output_dir}"
        )


@app.command()
def update(
    force_refresh: bool = typer.Option(
        True, help="Re-download cached data for affected years"
    ),
    verbose: bool = typer.Option(False, help="Print verbose output"),
):
    """
    Update recent data: re-download and convert the current year and,
    if before April, the previous year as well (to catch answers from
    the last three months).
    """
    today = datetime.date.today()
    years = [today.year]
    if today.month < 4:
        years.insert(0, today.year - 1)

    if verbose:
        print(f"Updating years: {years}")

    total_files = 0
    for year in years:
        total_files += _convert_year(year, force_refresh=force_refresh, verbose=verbose)

    if verbose:
        print(f"Done. Wrote {total_files} XML files to {output_dir}")


@app.command()
def convert_date_range(
    start_date: str = typer.Option(..., help="Start date in YYYY-MM-DD format"),
    end_date: str = typer.Option(..., help="End date in YYYY-MM-DD format"),
    force_refresh: bool = typer.Option(False, help="Re-download cached data"),
    verbose: bool = typer.Option(False, help="Print verbose output"),
):
    """
    Download and convert written questions for a specific date range.

    This command fetches questions from all years that might contain answers
    within the specified date range, then filters by answer date.
    """
    try:
        start = datetime.date.fromisoformat(start_date)
        end = datetime.date.fromisoformat(end_date)
    except ValueError as e:
        typer.echo(f"Error parsing dates: {e}", err=True)
        raise typer.Exit(1)

    if start > end:
        typer.echo("Start date must be before or equal to end date", err=True)
        raise typer.Exit(1)

    _convert_date_range(start, end, force_refresh=force_refresh, verbose=verbose)


def main():
    app()


if __name__ == "__main__":
    main()
