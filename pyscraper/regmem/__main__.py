import datetime

import click

from .commons import process as commons_process


@click.group()
def cli():
    pass


@cli.command()
@click.option("--chamber", type=str, default="commons")
@click.option("--force-refresh", is_flag=True)
@click.option("--quiet", is_flag=True)
def download_all_registers(
    chamber: str, force_refresh: bool = False, quiet: bool = False
):
    if chamber == "commons":
        commons_process.download_all_registers(force_refresh=force_refresh, quiet=quiet)
    else:
        raise ValueError(f"Unknown chamber: {chamber}")


@cli.command()
@click.option("--chamber", type=str, default="commons")
@click.option("--date", type=datetime.date)
@click.option("--force-refresh", is_flag=True)
@click.option("--quiet", is_flag=True)
def download_register_for_date(
    chamber: str, date: datetime.date, force_refresh: bool = False, quiet: bool = False
):
    if chamber == "commons":
        commons_process.download_register_from_date(
            date, force_refresh=force_refresh, quiet=quiet
        )
    else:
        raise ValueError(f"Unknown chamber: {chamber}")


@cli.command()
@click.option("--chamber", type=str, default="commons")
@click.option("--force-refresh", is_flag=True)
@click.option("--quiet", is_flag=True)
def download_latest_register(
    chamber: str, force_refresh: bool = False, quiet: bool = False
):
    if chamber == "commons":
        commons_process.download_latest_register(
            force_refresh=force_refresh, quiet=quiet
        )
    else:
        raise ValueError(f"Unknown chamber: {chamber}")


if __name__ == "__main__":
    cli()
