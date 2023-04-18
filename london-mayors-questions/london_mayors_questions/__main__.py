import datetime
from pathlib import Path
from typing import Optional

import rich_click as click

from .models import QuestionCollection

CLI_DATETIME_FORMAT = click.DateTime(formats=("%Y-%m-%d",))


@click.group(chain=True)
def cli():
    pass


@cli.command()
@click.option(
    "-s",
    "--start",
    type=CLI_DATETIME_FORMAT,
    help="The first date of the range to be scraped. (defaults to config's start date)",
)
@click.option(
    "-e",
    "--end",
    type=CLI_DATETIME_FORMAT,
    help="The last date of the range to be scraped. (defaults to today)",
)
@click.option("--last-week", is_flag=True, help="Scrape the last week")
@click.pass_context
def fetch_unknown_questions(
    context: click.Context,
    start: Optional[datetime.datetime] = None,
    end: Optional[datetime.datetime] = None,
    last_week: bool = False,
):
    """
    Update our list of known ids
    """
    qc = QuestionCollection()
    if last_week:
        start = datetime.datetime.now() - datetime.timedelta(days=7)
        end = datetime.datetime.now()
    qc.get_ids_for_date_range(start, end)
    qc.fetch_unstored_questions()


@cli.command()
@click.pass_context
def refresh_unanswered(context: click.Context):
    """
    Fetch all questions that have not been answered
    """
    QuestionCollection().get_unanswered_questions()


@cli.command()
@click.pass_context
def fetch_unstored(context: click.Context):
    """
    Fetch all questions that are known about but not downloaded.
    """
    QuestionCollection().fetch_unstored_questions()


@cli.command()
@click.option(
    "-o",
    "--outdir",
    type=click.Path(exists=False, file_okay=False, dir_okay=True),
    help="The directory to save the XMLs file to.",
    default=".",
)
@click.option(
    "-s",
    "--start",
    type=CLI_DATETIME_FORMAT,
    help="The first date of the range to be scrape.",
)
@click.option(
    "-e",
    "--end",
    type=CLI_DATETIME_FORMAT,
    help="The last date of the range to be scraped.",
)
@click.pass_context
def build_xml(
    context: click.Context,
    outdir: str,
    start: Optional[datetime.datetime] = None,
    end: Optional[datetime.datetime] = None,
):
    """
    Build the XML file
    """
    path = Path(outdir)

    if path.exists() is False:
        # make dir and parents
        path.mkdir(parents=True)
    if path.is_dir() is False:
        raise click.ClickException("outdir must be a directory")
    QuestionCollection().export_answers_to_xml(path, start, end)


@cli.command()
@click.pass_context
def unanswered_count(context: click.Context):
    """
    Get the number of unanswered questions
    """
    QuestionCollection().get_unanswered_count()


if __name__ == "__main__":
    cli()
