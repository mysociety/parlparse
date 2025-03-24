from typer import Typer

from .bluesky import update_bluesky
from .profiles import get_official_profile_urls

app = Typer()


@app.command(name="update-bluesky")
def update_bluesky_command():
    """
    Fetch House of Commons bluesky idents from list
    """
    update_bluesky()


@app.command()
def official_profiles():
    """
    Create a map from our person_ids to the official profile pages on various parliaments
    """
    get_official_profile_urls()


if __name__ == "__main__":
    app()
