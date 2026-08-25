"""Write supplemental Popolo and validate it with the main people file."""

from __future__ import annotations

from pathlib import Path

from mysoc_validator import Popolo


def write_and_cross_validate(
    supplemental: Popolo,
    output_path: Path,
    people_path: Path,
) -> Path:
    """Write a supplemental file, reload it with people.json, and validate it.

    Supplemental committee files intentionally omit people and shared chamber
    organizations. Reloading both files catches dangling references and checks
    the combined membership timelines that consumers will see.

    Validator 1.5.0 loads paths after the first with cross-checks disabled and
    does not revalidate after updating the base, so the explicit final
    ``model_validate`` is required.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    supplemental.to_path(output_path)

    combined = Popolo.from_path([people_path, output_path])
    Popolo.model_validate(combined.model_dump())
    return output_path
