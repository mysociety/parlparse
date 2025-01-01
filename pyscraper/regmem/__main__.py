import datetime

import click

from .commons import process as commons_process
from .ni import process as ni_process
from .scotland import process as scotland_process
from .wales import process as wales_process


@click.group()
def cli():
    pass


@cli.command()
@click.option("--chamber", type=str, default="commons")
@click.option("--force-refresh", is_flag=True)
@click.option("--quiet", is_flag=True)
@click.option("--no-progress", is_flag=True)
def download_all_registers(
    chamber: str,
    force_refresh: bool = False,
    quiet: bool = False,
    no_progress: bool = False,
):
    """
    Create all registers for a chamber - including fetching or trying to
    derive historical data where possible.
    """
    if chamber == "commons":
        commons_process.download_all_registers(
            force_refresh=force_refresh, quiet=quiet, no_progress=no_progress
        )
    elif chamber == "scotland":
        scotland_process.download_all_registers(
            force_refresh=force_refresh, quiet=quiet, no_progress=no_progress
        )
    elif chamber == "ni":
        ni_process.download_all_registers(
            force_refresh=force_refresh, quiet=quiet, no_progress=no_progress
        )
    elif chamber == "senedd":
        raise ValueError(
            "Can only fetch current register for Senedd - use 'download_latest_register'"
        )
    else:
        raise ValueError(f"Unknown chamber: {chamber}")


@cli.command()
@click.option("--chamber", type=str, default="commons")
@click.option("--date", type=datetime.date)
@click.option("--force-refresh", is_flag=True)
@click.option("--quiet", is_flag=True)
@click.option("--no-progress", is_flag=True)
def download_register_from_date(
    chamber: str,
    date: datetime.date,
    force_refresh: bool = False,
    quiet: bool = False,
    no_progress: bool = False,
):
    """
    Commons only process to fetch a specific date
    """
    if chamber == "commons":
        commons_process.download_register_from_date(
            date, force_refresh=force_refresh, quiet=quiet, no_progress=no_progress
        )
    else:
        raise ValueError(f"Unknown chamber: {chamber}")


@cli.command()
@click.option("--chamber", type=str, default="commons")
@click.option("--force-refresh", is_flag=True)
@click.option("--quiet", is_flag=True)
@click.option("--no-progress", is_flag=True)
def download_latest_register(
    chamber: str,
    force_refresh: bool = False,
    quiet: bool = False,
    no_progress: bool = False,
):
    """
    For each chamber, go through the logic to get any new registers.
    """
    if chamber == "commons":
        commons_process.download_latest_register(
            force_refresh=force_refresh, quiet=quiet, no_progress=no_progress
        )
    elif chamber == "scotland":
        scotland_process.download_all_registers(
            latest_only=True,
            force_refresh=force_refresh,
            quiet=quiet,
            no_progress=no_progress,
        )
    elif chamber == "ni":
        ni_process.download_all_registers(
            latest_only=True,
            force_refresh=force_refresh,
            quiet=quiet,
            no_progress=no_progress,
        )
    elif chamber == "senedd":
        wales_process.get_current_bilingual(
            force_refresh=force_refresh, quiet=quiet, no_progress=no_progress
        )
    else:
        raise ValueError(f"Unknown chamber: {chamber}")


@cli.command()
def convert_legacy_xml_to_json():
    """
    One-off command to convert the legacy XML files to the new JSON format.
    This is needed for consistent display logic on old MPs.
    """
    commons_process.convert_xml_folder()


if __name__ == "__main__":
    cli()
