"""
Produce the final XML file for Public Whip.
"""

from pathlib import Path
from typing import List

from lxml import etree

from .config import get_config
from .models import AnswerSegment


def build_xml_for_questions(answers: List[AnswerSegment]) -> etree._Element:
    """Given a date, collect answered questions and output the appropriate XML file."""
    config = get_config()

    pwxml = etree.Element("publicwhip")

    processed_response = []

    for answer in answers:
        question = answer.parent
        question_number = "{}.{}".format(
            answer.date.strftime("%Y-%m-%d"), question.safe_reference()
        )
        pw_root_id = "{}{}".format(
            config["public_whip_question_id_prefix"], question_number
        )

        q_a_hash = question.title + "".join(answer.response)

        # if we've already processed this question, skip it
        if q_a_hash in processed_response:
            print(f"skipping duplicate question {pw_root_id}")
            continue
        else:
            processed_response.append(q_a_hash)

        pw_heading_id = pw_root_id + ".h"
        heading_element = etree.SubElement(
            pwxml, "minor-heading", nospeaker="true", id=pw_heading_id
        )
        heading_element.text = question.title

        pw_question_id = pw_root_id + ".q0"
        question_element = etree.SubElement(
            pwxml,
            "question",
            id=pw_question_id,
            url=question.url,
            speakername=question.question_by,
            person_id=question.question_by_id(),
        )

        for paragraph in [question.safe_question_text()]:
            paragraph_element = etree.SubElement(question_element, "p")
            paragraph_element.text = paragraph

        for dialogue_index, dialogue in enumerate(answer.to_conversation()):
            pw_answer_id = pw_root_id + ".r" + str(dialogue_index)

            # if no speaker id we need to not pass one across at all to be handled correctly in twfy
            if dialogue.speaker_id == "uk.org.publicwhip/person/00000":
                id_dict = {}
            else:
                id_dict = {"person_id": dialogue.speaker_id}

            answer_element = etree.SubElement(
                pwxml,
                "reply",
                id=pw_answer_id,
                speakername=dialogue.speaker,
                **id_dict,
            )

            # append answer
            content = "\n".join(dialogue.text)
            content = "<container>" + content + "</container>"
            paragraph_xml = etree.fromstring(content)

            # delete any script tags so we're safe there in case london tries to hack us
            for script in paragraph_xml.xpath("//script"):  # type: ignore
                script.getparent().remove(script)

            # delete any style tags
            for style in paragraph_xml.xpath("//style"):  # type: ignore
                style.getparent().remove(style)

            # take each element under container and append it to the answer element
            for paragraph in paragraph_xml:
                answer_element.append(paragraph)

    return pwxml


def write_xml_to_file(lxml: etree._Element, output_file: Path):
    """Write an lxml element out to file."""

    # Make a new document tree
    tree = etree.ElementTree(lxml)

    # Write the XML file
    tree.write(
        str(output_file),
        encoding="utf-8",
        xml_declaration=True,
        pretty_print=True,
        with_tail=False,
    )
