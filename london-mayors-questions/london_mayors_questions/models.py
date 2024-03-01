"""
Model that stores the core concepts used in this scraper
"""

from __future__ import annotations

import datetime
import json
import time
from dataclasses import dataclass, field
from hashlib import md5
from itertools import groupby
from pathlib import Path
from typing import Iterator, List, Optional, Tuple

import pandas as pd
from rich import print
from tqdm import tqdm

from .config import get_config
from .membership import MembershipManager

cache_path = Path(__file__).parent.parent / "json_cache"


@dataclass
class Dialogue:
    """
    Connection of a speaker and list of paragraphs within an answer
    This is html from the source, and so includes tables etc
    """

    speaker: str
    date: datetime.datetime
    speaker_id: str = field(init=False)
    text: List[str] = field(default_factory=list)

    def __post_init__(self):
        membership_manager = MembershipManager()
        self.speaker_id = membership_manager.get_id_from_name(self.speaker, self.date)

    def to_dict(self):
        return {"speaker": self.speaker, "text": self.text}


@dataclass
class AnswerSegment:
    """
    Answer to a question, the response list is multiple lines rather than multiple responses.
    """

    response: List[str]
    date: datetime.datetime
    parent: QuestionPage

    def to_dict(self):
        return {
            "response": self.response,
            "date": self.date.isoformat(),
            "parent": self.parent.slug,
        }

    @classmethod
    def from_json(cls, json_obj: dict, parent: QuestionPage):
        json_obj["date"] = pd.to_datetime(json_obj["date"]).to_pydatetime()
        json_obj["parent"] = parent
        return cls(**json_obj)

    def holding_response(self) -> bool:
        """
        Return whether this is a holding response.
        In which case it's not a 'real' response yet and is ignored.
        """
        for line in self.response:
            if "officers are drafting a response" in line.lower():
                return True
        return False

    def to_conversation(self, include_question: bool = False):
        from .post_processing import convert_answer_to_dialogue

        if include_question:
            conversation = [self.parent.to_dialogue()]
        else:
            conversation = []

        conversation.extend(
            convert_answer_to_dialogue(self.response, self.parent.asked_of, self.date)
        )

        return conversation


@dataclass
class QuestionPage:
    """
    Question detailed from a URL
    """

    url: str
    slug: str
    title: str
    question_text: str
    meeting: str
    session_name: str
    question_by: str
    organisation: str
    reference: str = ""  # something this is missing for supplementary questions
    asked_of: str = "The Mayor"
    answers: List[AnswerSegment] = field(default_factory=lambda: [])
    category: str = ""

    def date_from_meeting(self) -> datetime.datetime:
        """
        Return the date of the meeting
        last three words will be something like 23 March 2023
        """
        date_str = " ".join(self.meeting.split()[-3:])
        return pd.to_datetime(date_str).to_pydatetime()

    def safe_reference(self) -> str:
        """
        Reference to use in final xml
        """
        if self.reference:
            year, in_year_ref = self.reference.split("/")
            return in_year_ref
        else:
            print(f"Warning: {self.slug} has no reference, using md5 hash of slug")
            return md5(self.slug.encode()).hexdigest()[:4]

    def safe_question_text(self) -> str:
        """
        Return the question text, but removes the name from the start
        """
        from .post_processing import text_amends

        if self.question_by in self.question_text[:30]:
            # position of first colon after the name
            colon_pos = self.question_text.find(":")
            t = self.question_text[colon_pos + 1 :]
        else:
            t = self.question_text

        return text_amends(t)

    def question_by_id(self) -> str:
        """return the publicwhip id for the person who asked the question"""
        membership_manager = MembershipManager()
        return membership_manager.get_id_from_name(
            self.question_by, self.date_from_meeting()
        )

    def to_dialogue(self) -> Dialogue:
        """
        Convert the original question to a dialogue
        """
        return Dialogue(
            speaker=self.question_by,
            text=[self.question_text],
            date=self.date_from_meeting(),
        )

    def add_answer(self, response: List[str], date: datetime.datetime):
        """
        Register an answer to this question
        """
        answer = AnswerSegment(response=response, date=date, parent=self)
        self.answers.append(answer)

    def final_answers(self) -> List[AnswerSegment]:
        """
        Return the final answer for each person
        """

        valid_answers = [x for x in self.answers if x.holding_response() is False]
        return valid_answers

    def unanswered(self) -> bool:
        """
        Return whether this question has been answered
        """
        return len(self.final_answers()) == 0

    def to_json(self):
        """
        Stash in the json_cache under the directory this file is in
        """
        stash_path = cache_path
        stash_path.mkdir(exist_ok=True)
        dest = stash_path / f"{self.slug}.json"
        with dest.open("w") as f:
            # get contents as dict
            di = self.__dict__.copy()
            # convert the answers to json
            di["answers"] = [x.to_dict() for x in di["answers"]]
            f.write(json.dumps(di, indent=4))

    @classmethod
    def from_json(cls, slug: str):
        """
        load from the json_cache under the directory this file is in
        """
        stash_path = Path(__file__).parent.parent / "json_cache" / f"{slug}.json"
        with stash_path.open("r") as f:
            contents = json.load(f)
        # convert the answers back to AnswerSegment
        answers = contents.pop("answers")
        question_page = cls(**contents)
        question_page.answers = [
            AnswerSegment.from_json(x, question_page) for x in answers
        ]
        return question_page

    @classmethod
    def fetch_question_details(cls, slug: str) -> QuestionPage:
        """
        fetch the question details from the london website
        """
        from .scraper import get_question_page

        attempts = 0
        while attempts < 5:
            try:
                item = get_question_page(slug)
                break
            except Exception as e:
                print(f"Error fetching {slug}: {e}")
                attempts += 1
                time.sleep(5)
        else:
            raise Exception(f"Failed to fetch {slug}")
        item.to_json()
        return item

    @classmethod
    def fetch_questions_on_id(cls, ids: List[str]):
        """
        fetch the details of a list of questions
        """
        for id in tqdm(ids):
            cls.fetch_question_details(id)
            time.sleep(1)


@dataclass
class QuestionCollection:
    ids: List[str] = field(default_factory=lambda: [])

    def __post_init__(self):
        self.ids = self.from_cache()

    def from_cache(self):
        id_file = cache_path / "ids.json"
        if id_file.exists():
            with id_file.open("r") as f:
                ids = json.load(f)
            return ids
        else:
            return []

    def save_cache(self):
        id_file = cache_path / "ids.json"
        cache_path.mkdir(exist_ok=True, parents=True)
        with id_file.open("w") as f:
            json.dump(self.ids, f, indent=4)

    def get_ids_for_date_range(
        self,
        start_date: Optional[datetime.datetime],
        end_date: Optional[datetime.datetime],
    ):
        """
        Query the london mayor website for the ids of questions within a date range
        """
        from .scraper import fetch_slugs

        if start_date is None:
            config = get_config()
            start_date = pd.to_datetime(config["default_start_date"]).to_pydatetime()
        if end_date is None:
            end_date = datetime.datetime.now()

        # breakdown the date range into weeks
        weeks = pd.date_range(start_date, end_date, freq="W")
        for week in weeks:
            week_start_date = week.to_pydatetime()
            week_end_date = (week + pd.DateOffset(days=7)).to_pydatetime()
            new_ids = fetch_slugs(week_start_date, week_end_date)
            new_ids = [x for x in new_ids if x not in self.ids]

            # special case for a very duplicated supplemntary question
            new_ids = [
                x
                for x in new_ids
                if ("oral-update-mayors-report-supplementary-1" not in x)
                or x == "oral-update-mayors-report-supplementary-1-30"
            ]
            self.ids.extend(new_ids)
            self.save_cache()

    def fetch_unstored_questions(self):
        """
        Given known ids - refresh any that are not in the cache
        """
        to_refresh = []
        for slug in self.ids:
            stash_path = cache_path / f"{slug}.json"
            if not stash_path.exists():
                to_refresh.append(slug)
        print("[blue]Fetching new questions[/blue]")
        QuestionPage.fetch_questions_on_id(to_refresh)

    def get_unanswered_questions(self):
        """
        Given known ids - refresh any that are unanswered
        """
        to_refresh = []
        for slug in self.ids:
            q = QuestionPage.from_json(slug)
            if q.unanswered():
                to_refresh.append(slug)
        print("[blue]Refreshing unanswered questions[/blue]")
        QuestionPage.fetch_questions_on_id(to_refresh)

    def get_unanswered_count(self):
        """
        Get the number of unanswered questions
        """
        count = 0
        for slug in self.ids:
            q = QuestionPage.from_json(slug)
            if q.unanswered():
                count += 1
        print(f"[blue]{count} unanswered questions out of {len(self.ids)}[/blue]")

    def group_by_date(
        self,
        start_date: Optional[datetime.datetime],
        end_date: Optional[datetime.datetime],
    ) -> Iterator[Tuple[datetime.datetime, List[AnswerSegment]]]:
        """
        Get all answeres grouped by date to pass to xml
        """

        config = get_config()
        if start_date is None:
            start_date = pd.to_datetime(config["default_start_date"]).to_pydatetime()
        if end_date is None:
            end_date = datetime.datetime.now()

        answers = []
        for slug in self.ids:
            q = QuestionPage.from_json(slug)
            answers.extend(q.final_answers())

        answers = sorted(answers, key=lambda x: x.date)
        for date, group in groupby(answers, key=lambda x: x.date):
            if start_date <= date <= end_date:
                yield date, list(group)

    def export_answers_to_xml(
        self,
        output_dir: Path,
        start_date: Optional[datetime.datetime],
        end_date: Optional[datetime.datetime],
    ):
        """
        Export all answers to xml
        Answers are exported based on the date they were received, rather than when the question was asked
        """
        from .xml import build_xml_for_questions, write_xml_to_file

        for date, answers in self.group_by_date(start_date, end_date):
            print(f"[blue]Exporting answers for {date}[/blue]")
            file_name = f"lmqs{date.strftime('%Y-%m-%d')}.xml"
            xml = build_xml_for_questions(answers)
            write_xml_to_file(xml, output_dir / file_name)
