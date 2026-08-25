"""
Shared person resolution for committee and parliamentary post scrapers.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import date
from typing import Optional

from mysoc_validator import Popolo
from mysoc_validator.models.popolo import IdentifierScheme, LordName, Person

from .iterables import unique

FallbackMatcher = Callable[[str, Popolo], Optional[str]]


def person_display_names(person: Person) -> list[str]:
    """
    Return the display-name variants supplied by the Popolo models.
    """
    values: list[str] = []
    for other_name in person.names:
        if isinstance(other_name, LordName):
            values.extend(other_name.name_variants())
        else:
            values.append(other_name.nice_name())
    return values


def unique_person_id_by_name(name: str, people: Popolo) -> str | None:
    """
    Return a person only when a case-insensitive global name match is unique.
    """
    normalized = name.casefold()
    matches = {
        person.id
        for person in people.persons
        if any(value.casefold() == normalized for value in person_display_names(person))
    }
    return next(iter(matches)) if len(matches) == 1 else None


def resolve_person_id(
    people: Popolo,
    *,
    context: str,
    source_identifier: str | int | None = None,
    identifier_scheme: IdentifierScheme | str | None = None,
    names: Iterable[str] = (),
    chamber_id: str | None = None,
    on_date: date | None = None,
    include_historical_names: bool = False,
    fallback: FallbackMatcher | None = None,
) -> str:
    """
    Resolve a source person to a TWFY person ID.

    Official identifiers are preferred. Dated chamber name matching uses
    mysoc-validator and can optionally include every historical name of people
    eligible for the chamber on that date. A caller may provide a conservative
    source-specific fallback for people outside the chamber membership index.
    """
    attempted_names = tuple(unique(name.strip() for name in names if name.strip()))

    if source_identifier is not None and identifier_scheme is not None:
        try:
            return people.persons.from_identifier(
                str(source_identifier), scheme=identifier_scheme
            ).id
        except ValueError:
            pass

    if chamber_id is not None and on_date is not None:
        for name in attempted_names:
            person = people.persons.from_name(
                name,
                chamber_id=chamber_id,
                date=on_date,
                include_historical_names=include_historical_names,
            )
            if person is not None:
                return person.id

    if fallback is not None:
        matches = {
            person_id
            for name in attempted_names
            if (person_id := fallback(name, people)) is not None
        }
        if len(matches) == 1:
            return matches.pop()

    identifier = (
        f"{identifier_scheme} {source_identifier}"
        if source_identifier is not None and identifier_scheme is not None
        else "no source identifier"
    )
    names_text = ", ".join(repr(name) for name in attempted_names) or "no names"
    raise ValueError(f"Could not resolve {context}: {identifier}; {names_text}")
