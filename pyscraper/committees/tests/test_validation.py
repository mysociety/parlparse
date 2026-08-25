import json
from pathlib import Path

import pytest
from mysoc_validator import Popolo

from pyscraper.committees.helpers.validation import write_and_cross_validate


def people() -> Popolo:
    return Popolo.model_validate(
        {
            "persons": [
                {
                    "id": "uk.org.publicwhip/person/1",
                    "other_names": [
                        {
                            "given_name": "Jane",
                            "family_name": "Doe",
                            "note": "Main",
                        }
                    ],
                }
            ]
        }
    )


def supplemental(person_id: str) -> Popolo:
    return Popolo.model_validate(
        {
            "organizations": [{"id": "committee-1", "name": "Committee"}],
            "memberships": [
                {
                    "id": "membership/1",
                    "person_id": person_id,
                    "organization_id": "committee-1",
                }
            ],
        },
        context={"skip_cross_checks": True},
    )


def test_writes_and_cross_validates_supplemental_popolo(tmp_path: Path) -> None:
    people_path = tmp_path / "people.json"
    output_path = tmp_path / "committees.json"
    people().to_path(people_path)

    result = write_and_cross_validate(
        supplemental("uk.org.publicwhip/person/1"), output_path, people_path
    )

    assert result == output_path
    assert output_path.exists()
    emitted = json.loads(output_path.read_text())
    assert emitted["organizations"] == [{"id": "committee-1", "name": "Committee"}]
    assert emitted["memberships"] == [
        {
            "id": "membership/1",
            "organization_id": "committee-1",
            "person_id": "uk.org.publicwhip/person/1",
        }
    ]


def test_rejects_a_supplemental_membership_for_an_unknown_person(
    tmp_path: Path,
) -> None:
    people_path = tmp_path / "people.json"
    output_path = tmp_path / "committees.json"
    people().to_path(people_path)

    output_path.write_text('{"existing": true}')
    with pytest.raises(
        ValueError, match="Generated committee output failed cross-validation"
    ) as error:
        write_and_cross_validate(
            supplemental("uk.org.publicwhip/person/999"), output_path, people_path
        )

    assert "invalid person uk.org.publicwhip/person/999" in str(error.value.__cause__)
    # A failed update must leave the preceding valid artifact untouched.
    assert output_path.read_text() == '{"existing": true}'
