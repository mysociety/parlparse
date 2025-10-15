from __future__ import annotations

import datetime
import json
import re
import unicodedata
from pathlib import Path
from typing import Optional

import duckdb
import pandas as pd
from mysoc_validator import Popolo
from mysoc_validator.models.consts import Chamber
from tqdm import tqdm

from pyscraper.settings import settings

from .models import AutoAnnotationList, SpeechNLP, Transcript


def extract_isodate(text: str) -> Optional[datetime.date]:
    """
    Get date from filename
    """
    pattern = r"(?<!\d)(?<!\d-)(\d{4})-(\d{2})-(\d{2})(?!-\d)(?!\d)"
    re_match = re.search(pattern, text)
    if re_match:
        year, month, day = map(int, re_match.groups())
        try:
            return datetime.date(year, month, day)
        except ValueError:
            return None
    return None


def wikipedia_properties(items: list[str]):
    """
    Fetch any wikipedia pages that are a direct match for the given titles
    """
    page_with_redirect = (
        settings.parldata_path / "wikilinks" / "page_with_redirect.parquet"
    )

    if not page_with_redirect.exists():
        raise FileNotFoundError(
            f"Parquet file with Wikipedia data not found at {page_with_redirect}. "
            "Please run the create_wikipedia_table script to generate it."
        )

    df = pd.DataFrame(items, columns=["page_title"])

    duck = duckdb.connect()

    duck.register("source_data", df)

    duck.execute(f"CREATE OR REPLACE VIEW page as SELECT * FROM '{page_with_redirect}'")
    query = """
        SELECT page_title: page.final_page_title,
               wikibase_shortdesc
        FROM page
        JOIN source_data ON page.page_title = source_data.page_title
        WHERE page.disambiguation = False
    """
    return duck.execute(query).df().to_dict(orient="records")


def wiki_title(s: str) -> str:
    """
    Converted from PHP function in TWFY - normalise to English
    Wikipedia rules
    """
    # 1) trim + normalize unicode

    # if it starts with a non uppercase 'The ' take it out
    if s.startswith("the "):
        s = s[4:]

    s = unicodedata.normalize("NFC", s.strip())

    # 2) collapse any whitespace runs to a single space
    s = re.sub(r"\s+", " ", s)

    # 3) remove leading/trailing underscores/spaces around colons
    s = re.sub(r"\s*:\s*", ":", s)

    # 4) if there's a namespace ("Foo:Bar"), capitalize only the first char of the page part
    if ":" in s:
        ns, page = s.split(":", 1)
        ns = ns.strip()  # namespaces are case-insensitive on enwiki
        page = page.strip()
        if page:
            page = page[0].upper() + page[1:]
        s = f"{ns}:{page}"
    else:
        # Capitalize first character of the title (wgCapitalLinks behavior)
        if s:
            s = s[0].upper() + s[1:]

    # 5) convert spaces to underscores (URL/display form commonly seen)
    s = s.replace(" ", "_")

    # 6) collapse multiple underscores and strip stray underscores
    s = re.sub(r"_+", "_", s).strip("_")

    return s


def fast_checks(items: AutoAnnotationList):
    """
    Quick check for invalid links
    """
    short_word_rule = re.compile(r"^(?![A-Z]{2,6}$)[A-Z][a-zA-Z]{0,5}$")

    banned_list = ["Government"]

    for i in items.iter_active():
        if len(i.phrase) <= 6 and short_word_rule.match(i.phrase):
            i.discarded = True
            i.discard_reason = "Failed fast checks - short word"

        # remove all one word phrases that aren't all caps
        if len(i.phrase.split()) == 1 and not i.phrase.isupper():
            i.discarded = True
            i.discard_reason = "Failed fast checks - one word non-all-caps"

        if i.phrase in banned_list:
            i.discarded = True
            i.discard_reason = "Failed fast checks - banned phrase"

    return items


def check_wikipedia(items: AutoAnnotationList):
    """
    Check all active items against wikipedia direct matches
    """
    from .models import MatchType

    titles = list(set([wiki_title(i.phrase) for i in items.iter_active()]))
    results = wikipedia_properties(titles)
    title_to_result = {r["page_title"]: r for r in results}

    for i in items.iter_active():
        norm_title = wiki_title(i.phrase)
        if norm_title in title_to_result:
            res = title_to_result[norm_title]
            i.link = f"https://en.wikipedia.org/wiki/{res['page_title']}"
            i.foreign_id = res["page_title"]
            i.foreign_short_desc = res["wikibase_shortdesc"]
            i.match_type = MatchType.WIKIPEDIA
        else:
            i.discarded = True
            i.discard_reason = "No Wikipedia match"

    return items


def remove_direct_name_links(items: AutoAnnotationList, date: datetime.date):
    """
    Remove direct name links to persons in parliament (this is handled in twfy itself)
    """
    popolo = Popolo.from_path(settings.memberdata_path / "people.json")

    for i in items.iter_active():
        if popolo.persons.from_name(i.phrase, chamber_id=Chamber.COMMONS, date=date):
            i.discarded = True
            i.discard_reason = "Direct name link to person in parliament"

    return items


def discard_same_links_in_same_speech(items: AutoAnnotationList):
    """
    Remove duplicate links in the same speech (for our purposes don't need to check twice)
    """
    seen_links = set()
    for i in items.iter_active():
        if i.speech_id and i.link:
            key = (i.speech_id, i.link)
            if key in seen_links:
                i.discarded = True
                i.discard_reason = "Duplicate link in same speech"
            else:
                seen_links.add(key)
    return items


def check_wikipedia_in_context(items: AutoAnnotationList):
    """
    Check all active items against Wikipedia context using an LLM
    """
    from .relevance_agent import LinkClassification, combined_wikipedia_check

    active_count = items.active_count()
    previously_invalid = []

    for i in tqdm(
        items.iter_active(), desc="Checking wiki context", total=active_count
    ):
        if i.phrase in previously_invalid:
            i.discarded = True
            i.discard_reason = "Phrase marked too general in earlier item"
            continue
        if i.foreign_short_desc:
            reason = combined_wikipedia_check(
                paragraph=i.source_paragraph,
                title=i.phrase,
                desc=i.foreign_short_desc,
            )
            if reason.link_status == LinkClassification.wrong_article:
                i.discarded = True
                i.discard_reason = f"Link not relevant: {reason.explanation}"
            elif reason.link_status == LinkClassification.article_too_general:
                i.discarded = True
                i.discard_reason = f"Link too general: {reason.explanation}"
                previously_invalid.append(i.phrase)

    return items


def iter_all_annotations():
    annotations_folder = settings.parldata_path / "wikilinks" / "annotations"

    for file in annotations_folder.glob("annotations_*.json"):
        al = AutoAnnotationList.from_path(file)
        yield from al


def export_lists():
    """
    Export allowlist and blocklist of Wikipedia links.
    """
    allowlist = set()
    blocklist = set()

    lists_dir = settings.parldata_path / "wikilinks" / "lists"

    if not lists_dir.exists():
        lists_dir.mkdir(parents=True, exist_ok=True)

    blocklist_path = lists_dir / "blocklist.json"
    allowlist_path = lists_dir / "allowlist.json"

    for a in iter_all_annotations():
        if a.discarded:
            blocklist.add(wiki_title(a.phrase))
        allowlist.add(wiki_title(a.phrase))

    # Remove any items from the allowlist that are also in the blocklist
    allowlist.difference_update(blocklist)

    with blocklist_path.open("w") as f:
        json.dump(sorted(list(blocklist)), f, indent=2)

    with allowlist_path.open("w") as f:
        json.dump(sorted(list(allowlist)), f, indent=2)


class TranscriptProcesssor:
    def __init__(self):
        self.nlp = SpeechNLP()

    def process_transcript_pattern(
        self,
        folder: str,
        pattern: str,
        include_relevance_check: bool = False,
        override: bool = False,
    ):
        xml_dir = settings.parldata_path / "scrapedxml" / folder
        for file in xml_dir.glob(pattern):
            print(file)
            print(f"Processing {file}")
            self.process_transcript(
                file, include_relevance_check=include_relevance_check, override=override
            )

    def process_relevance_check(self, pattern: str, skip_if_any: bool = True):
        annotations_folder = settings.parldata_path / "wikilinks" / "annotations"

        for file in annotations_folder.glob(f"annotations_{pattern}.json"):
            al = AutoAnnotationList.from_path(file)
            if skip_if_any and any(
                x for x in al.iter_active() if x.discard_reason.startswith("Link")
            ):
                print(f"Skipping {file} as it already has relevance checks")
                continue
            al = check_wikipedia_in_context(al)
            al.to_path(file)

    def process_transcript(
        self,
        transcript_path: Path,
        include_relevance_check: bool = False,
        override: bool = False,
    ):
        annotations_folder = settings.parldata_path / "wikilinks" / "annotations"

        if not annotations_folder.exists():
            annotations_folder.mkdir(parents=True, exist_ok=True)

        file_name = transcript_path.stem
        parent_folder = transcript_path.parent.name
        debate_date = extract_isodate(file_name)
        if debate_date is None:
            raise ValueError(f"Could not extract date from filename: {file_name}")

        dest = annotations_folder / f"annotations_{parent_folder}_{file_name}.json"

        if dest.exists() and not override:
            return

        transcript = Transcript.from_xml_path(transcript_path)

        annotations = self.nlp.extract_entities_from_transcript(transcript)

        annotations = fast_checks(annotations)
        annotations = check_wikipedia(annotations)
        annotations = remove_direct_name_links(annotations, debate_date)
        if include_relevance_check:
            annotations = check_wikipedia_in_context(annotations)
        annotations = discard_same_links_in_same_speech(annotations)
        annotations.to_path(dest)
