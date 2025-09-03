from typer import Typer

from .commons import fetch_and_update, initial_populate, to_parquet

app = Typer(pretty_exceptions_enable=False)


@app.command(name="initial")
def app_initial_populate():
    """
    Fetch and save all proposals from the start date to today.
    """
    initial_populate()


@app.command(name="update")
def app_fetch_and_update(quiet: bool = False):
    """
    Fetch and update the proposals from the last 90 days.
    """
    fetch_and_update(quiet=quiet)


@app.command(name="parquet")
def app_to_parquet():
    """
    Convert the proposals to parquet format.
    """
    to_parquet()


if __name__ == "__main__":
    app()
