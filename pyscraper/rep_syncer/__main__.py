"""
CLI for the rep_syncer package.

Usage:
  python -m pyscraper.rep_syncer sp run [--people PATH] [--dry-run] [--quiet]
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from mysoc_validator import Popolo
from rich import print

from .sp import (
    fetch_sp_memberships,
    sync_sp_memberships,
)

app = typer.Typer(pretty_exceptions_enable=False)
sp_app = typer.Typer(pretty_exceptions_enable=False)
app.add_typer(sp_app, name="sp", help="Scottish Parliament sync commands.")


def default_people_path() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "members" / "people.json"
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        "Could not find members/people.json in any parent directory."
    )


@sp_app.command()
def run(
    people: Optional[Path] = typer.Option(None, help="Path to people.json."),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Print changes but do not write people.json."
    ),
    quiet: bool = typer.Option(
        False, "--quiet", help="Suppress progress messages; only print sync log."
    ),
) -> None:
    """Fetch from the SP API and sync against people.json."""
    people_path = people or default_people_path()

    if not quiet:
        print("[bold]Fetching SP data…[/bold]")
    sp_memberships = fetch_sp_memberships(verbose=not quiet)

    if not quiet:
        print(f"Loading people.json from [cyan]{people_path}[/cyan]")
    popolo = Popolo.from_path(people_path, cross_validate=False)

    log = sync_sp_memberships(sp_memberships, popolo)

    if not quiet:
        for line in log:
            print(line)

    if dry_run:
        if not quiet:
            print("\n[dim][dry-run] No changes written.[/dim]")
    else:
        popolo.to_path(people_path)
        if not quiet:
            print(f"\nWrote updated people.json to [cyan]{people_path}[/cyan]")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
