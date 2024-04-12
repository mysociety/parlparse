"""
Text post processing features - which can be run on text after it has been cached
"""


from __future__ import annotations

import datetime
import re
from typing import List

from bs4 import BeautifulSoup

from .config import get_config
from .models import Dialogue


def remove_partial_tags(text: str) -> str:
    """
    this string may contain html tags that do not have an equiv
    opening or closing tag.
    we want to remove all of these using regex
    """

    # remove any html tags
    text = re.sub(r"<[^>]*>", "", text)

    return text


def remove_opening_closing_tags(text: str) -> str:
    """
    because we've split it, we're sometimes opening with a series of closing html tags
    let's get rid of those
    """

    # remove any closed html tags as the start of the string and do it until there are none left
    while re.match(r"^</[^>]*>", text):
        text = re.sub(r"^</[^>]*>", "", text)

    return text


def remove_empty_tags(text: str) -> str:
    """
    Given a html text, remove any span or p tags that are empty or just contain whitespace
    """
    soup = BeautifulSoup(text, "html.parser")
    for tag in soup.find_all(["span", "p"]):
        if not tag.text:
            tag.decompose()
        # if a span exists with some whitespace inside, remove it and replace with a space
        if tag.name == "span" and re.match(r"^\s+$", tag.text):
            tag.replace_with(" ")

    # check all remaining spans, and if spans are not a child or grandchild of a p tag, promote them to a p tag
    for tag in soup.find_all("span"):
        if tag.find_parent("p") is None:
            tag.name = "p"

    # for all remaining span tags, delete and move the contents a level up
    for tag in soup.find_all("span"):
        tag.unwrap()

    # for all tags, remove all class attributes
    for tag in soup.find_all(True):
        del tag["class"]

    return str(soup)


def text_amends(text: str) -> str:
    """
    Fix whitespace in text and other bulk fixes
    """
    text = text.replace("\xa0", " ").replace("  ", " ").strip()
    text = text.replace("\u00A0", " ")
    text = text.replace("\u2019", "'")
    text = text.replace('href="/', 'href="https://www.london.gov.uk/').strip()
    return text


def convert_answer_to_dialogue(
    answer: List[str], asked_of: str, date: datetime.datetime
) -> List[Dialogue]:
    """
    Convert a list of lines of text into a list of Dialogue objects
    """
    config = get_config()

    office_label = None
    for k, v in config["office_map"].items():
        if k.lower() in asked_of.lower():
            office_label = v
            break
        if v.lower() in asked_of.lower():
            office_label = v
            break

    if office_label is None:
        raise Exception("Unable to find office label for {}".format(asked_of))

    answer_whole = "\n".join(answer)
    # add extra new lines after </p> tags
    answer_whole = answer_whole.replace("</p>", "</p>\n")
    answer_whole = answer_whole.replace("<strong><span>", "\n<strong><span>")
    answer = answer_whole.split("\n")

    # break lines into pairs of speaker and text (use None for speaker if there isn't a change of speaker)
    speaker_text_pairs = []
    for line in answer:
        if ":" in line:
            speaker, text = line.split(":", 1)
            is_office_holder = False
            for k, v in config["office_map"].items():
                if k in speaker[:70] or v in speaker[:70]:
                    is_office_holder = True
            if is_office_holder or (" AM" in speaker and len(speaker) < 70):
                speaker = speaker
                text = text_amends(text)
                # if present, remove <p><strong> from speaker and </strong> from the start of text

                text = remove_opening_closing_tags(text)
                if "<p>" in speaker:
                    text = "<p>" + text
                speaker = remove_partial_tags(speaker)
            else:
                text = text_amends(line)
                speaker = None
        else:
            text = text_amends(line)
            speaker = None
        speaker_text_pairs.append((speaker, text))

    # convert pairs into dialogue
    dialogue = []
    for speaker, text in speaker_text_pairs:
        if speaker is None:
            if len(dialogue) == 0:
                dialogue.append(Dialogue(speaker=office_label, text=[text], date=date))
            else:
                dialogue[-1].text.append(text)
        else:
            dialogue.append(Dialogue(speaker=speaker, text=[text], date=date))

    for d in dialogue:
        d.text = [x.strip() for x in d.text if x.strip() != ""]
        all_text = "\n".join(d.text)
        all_text = remove_empty_tags(all_text)
        d.text = all_text.split("\n")

    return dialogue
