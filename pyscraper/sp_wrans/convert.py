"""
Convert Scottish Parliament written questions/answers to
TheyWorkForYou XML format.

Uses mysoc_validator transcript models to build the XML output.
"""

from __future__ import annotations

import datetime
import re
from functools import lru_cache
from itertools import groupby
from pathlib import Path
from typing import Optional

from mysoc_validator import Popolo
from mysoc_validator.models.consts import Chamber, IdentifierScheme
from mysoc_validator.models.transcripts import (
    MajorHeading,
    MinorHeading,
    Question,
    Reply,
    SpeechItem,
    Transcript,
)
from mysoc_validator.models.xml_base import MixedContentHolder

from pyscraper.regmem.funcs import memberdata_path

from .api_models import SPQuestion
from .cleanup import clean_text
from .text_processing import text_to_speech_items

SP_QUESTION_URL = (
    "https://www.parliament.scot/chamber-and-committees/"
    "questions-and-answers/question?ref={event_id}"
)

GID_PREFIX = "uk.org.publicwhip/spwa"


@lru_cache
def get_popolo() -> Popolo:
    return Popolo.from_path(memberdata_path / "people.json")


def person_id_from_scot_parl_id(scot_parl_id: int) -> Optional[str]:
    """
    Convert a Scottish Parliament MSP ID to a TWFY person ID.
    """
    popolo = get_popolo()
    try:
        person = popolo.persons.from_identifier(
            str(scot_parl_id), scheme=IdentifierScheme.SCOTPARL
        )
    except ValueError:
        return None
    if person:
        return person.id
    return None


def speaker_name_from_scot_parl_id(
    scot_parl_id: int, date: datetime.date
) -> Optional[str]:
    """
    Get the display name for an MSP from their Scottish Parliament ID.
    """
    popolo = get_popolo()
    try:
        person = popolo.persons.from_identifier(
            str(scot_parl_id), scheme=IdentifierScheme.SCOTPARL
        )
    except ValueError:
        return None
    if person:
        name = person.get_main_name(date)
        if name:
            return name.nice_name()
    return None


def person_id_from_name(name: str, date: datetime.date, verbose: bool = False) -> str:
    """
    Try to resolve an MSP name to a TWFY person ID using Popolo name matching.
    Falls back to uk.org.publicwhip/person/0 if not found.
    """
    popolo = get_popolo()
    # Clean up double spaces sometimes present in the API data
    clean_name = re.sub(r"\s+", " ", name).strip()
    # Strip any "(on behalf of ...)" suffixes
    clean_name = re.sub(r"\s*\(on behalf of.*\)", "", clean_name).strip()
    try:
        person = popolo.persons.from_name(
            clean_name,
            chamber_id=Chamber.SCOTLAND,
            date=date,
        )
        if person:
            return person.id
    except (ValueError, KeyError):
        pass
    if verbose:
        print(f"Warning: Could not resolve answerer name '{name}' to a person ID")
    return "uk.org.publicwhip/person/0"


def build_transcript_for_date(
    questions: list[SPQuestion],
    answer_date: datetime.date,
    verbose: bool = False,
) -> Transcript:
    """
    Build a Transcript object for all questions answered on a given date.
    """
    items: list = []
    major_heading_counter = 0

    # Add the top-level major heading
    date_str = answer_date.strftime("%A %d %B %Y")
    major_id = f"{GID_PREFIX}/{answer_date.isoformat()}.{major_heading_counter}.mh"
    items.append(
        MajorHeading(
            id=major_id,
            nospeaker="true",
            url="",
            content=MixedContentHolder(
                text=f"Written Answers {date_str}",
                raw=f"Written Answers {date_str}",
            ),
        )
    )
    major_heading_counter += 1

    # Add "Scottish Government" major heading
    major_id = f"{GID_PREFIX}/{answer_date.isoformat()}.{major_heading_counter}.mh"
    items.append(
        MajorHeading(
            id=major_id,
            nospeaker="true",
            url="",
            content=MixedContentHolder(
                text="Scottish Government",
                raw="Scottish Government",
            ),
        )
    )

    # Sort questions by event_id for consistent ordering
    questions = sorted(questions, key=lambda q: q.event_id)

    missing_ids: list[int] = []

    for question in questions:
        event_id = question.event_id
        question_url = SP_QUESTION_URL.format(event_id=event_id)

        # Minor heading per question (using the title as heading text)
        minor_id = f"{GID_PREFIX}/{answer_date.isoformat()}.{event_id}.h"
        heading_text = clean_text(question.title)
        items.append(
            MinorHeading(
                id=minor_id,
                nospeaker="true",
                url=question_url,
                content=MixedContentHolder(text=heading_text, raw=heading_text),
            )
        )

        # Question element
        asker_person_id = person_id_from_scot_parl_id(question.msp_id)
        if asker_person_id is None:
            if question.msp_id not in missing_ids:
                missing_ids.append(question.msp_id)
                if verbose:
                    print(
                        f"Warning: Could not find TWFY person ID for "
                        f"MSPID {question.msp_id}"
                    )
            asker_person_id = "unknown"

        asker_name = speaker_name_from_scot_parl_id(question.msp_id, answer_date)
        if asker_name is None:
            asker_name = f"MSPID {question.msp_id}"

        ques_id = f"{GID_PREFIX}/{answer_date.isoformat()}.{event_id}.q0"
        ques_items = text_to_speech_items(question.item_text, qnum=event_id)

        # Add "registered interest" declaration if applicable
        if question.registered_interest:
            interest_text = "An interest was declared."
            ques_items.insert(
                0,
                SpeechItem.model_validate(
                    {
                        "tag": "p",
                        "class": "interest-declaration",
                        "content": MixedContentHolder(
                            text=interest_text, raw=interest_text
                        ),
                    }
                ),
            )

        items.append(
            Question(
                id=ques_id,
                speakername=asker_name,
                person_id=asker_person_id,
                spid=event_id,
                url=question_url,
                items=ques_items,
            )
        )

        # Reply element
        answerer_name = question.answered_by_msp or "Scottish Government"
        # Resolve answerer name to person_id, falling back to person/0
        if answerer_name and answerer_name != "Scottish Government":
            answerer_person_id = person_id_from_name(
                answerer_name, answer_date, verbose=verbose
            )
        else:
            answerer_person_id = "uk.org.publicwhip/person/0"

        reply_id = f"{GID_PREFIX}/{answer_date.isoformat()}.{event_id}.r0"
        reply_items = text_to_speech_items(question.answer_text or "")
        items.append(
            Reply(
                id=reply_id,
                speakername=answerer_name,
                person_id=answerer_person_id,
                url=question_url,
                items=reply_items,
            )
        )

    return Transcript(items=items)


def convert_questions_to_xml(
    questions: list[SPQuestion],
    output_dir: Path,
    verbose: bool = False,
) -> list[Path]:
    """
    Convert a list of answered written questions into per-day XML files.

    Groups questions by answer date and writes one XML file per day.
    Returns list of paths written.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Group questions by answer date
    sorted_questions = sorted(
        questions, key=lambda q: q.answer_date_only or datetime.date.min
    )
    written_paths = []

    for answer_date, group in groupby(
        sorted_questions, key=lambda q: q.answer_date_only
    ):
        if answer_date is None:
            continue

        day_questions = list(group)
        transcript = build_transcript_for_date(
            day_questions, answer_date, verbose=verbose
        )

        filename = f"spwa{answer_date.isoformat()}.xml"
        dest_path = output_dir / filename
        transcript.to_xml_path(dest_path)
        written_paths.append(dest_path)

        if verbose:
            print(
                f"Wrote {len(day_questions)} questions for {answer_date} to {dest_path}"
            )

    return written_paths
