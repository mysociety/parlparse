"""Write supplemental Popolo and validate it with the main people file."""

from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile

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
    with NamedTemporaryFile(
        dir=output_path.parent,
        prefix=f".{output_path.name}.",
        suffix=".tmp",
        delete=False,
    ) as temporary_file:
        temporary_path = Path(temporary_file.name)
    try:
        supplemental.to_path(temporary_path)
        try:
            combined = Popolo.from_path([people_path, temporary_path])
            Popolo.model_validate(combined.model_dump())
        except ValueError as exc:
            raise ValueError(
                "Generated committee output failed cross-validation; "
                f"output={output_path}; people={people_path}"
            ) from exc
        temporary_path.replace(output_path)
    finally:
        temporary_path.unlink(missing_ok=True)
    return output_path
