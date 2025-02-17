"""
This handles bi-directional conversions between the XML based regmem format and the new JSON based format.

We need to go in both directions because the XML format is still used for comparions over time.
"""

from __future__ import annotations

import datetime

from jinja2 import Template
from mysoc_validator.models import xml_interests
from mysoc_validator.models.consts import Chamber
from mysoc_validator.models.interests import (
    RegmemCategory,
    RegmemDetail,
    RegmemEntry,
    RegmemPerson,
    RegmemRegister,
)
from mysoc_validator.models.xml_base import MixedContentHolder

from .funcs import parldata_path

detail_template = Template(
    """
        <li class="interest-detail">
            <span class="interest-detail-name">{{ detail.display_as|e  }}: </span>
            {% if detail.type == "container" %}
            {% for group in detail.value %}
             <ul class="interest-detail-values-groups">
                {% for value in group %}
                    {{ detail_to_html(value) }}
                {% endfor %}
                </ul>
            {% endfor %}
            {% else %}
                <span class="interest-detail-value">{{ detail.value|e }}</span>
            {% endif %}

               
        </li>
        """
)

interest_template = Template(
    """
        <div class="interest-item" id="{{ interest.comparable_id }}">
        {% if interest.content %}
            {% if interest.info_type == "subentry" %}
                <h6 class="interest-summary">{{ interest.content|e }}</h6>
            {% else %}
                <h4 class="interest-summary">{{ interest.content|e }}</h4>
            {% endif %}
        {% endif %}
            <ul class="interest-details-list">
            {% for detail in interest.details %}
                {% if detail.value %}
                    {{ detail_to_html(detail) }}
                {% endif %}
            {% endfor %}
                {% if interest.date_registered %}
                <li class="registration-date">Registration Date: {{ interest.date_registered.strftime('%d %B %Y') }}</li>
                {% endif %}
                {% if interest.date_published %}
                <li class="published-date">Published Date: {{ interest.date_published.strftime('%d %B %Y') }}</li>
                {% endif %}
                {% if interest.date_updated %}
                <li class="last-updated-date">Last Updated Date: {{ interest.date_updated.strftime('%d %B %Y') }}</li>
                {% endif %}
                {% if interest.date_received %}
                <li class="received-date">Received Date: {{ interest.date_received.strftime('%d %B %Y') }}</li>
                {% endif %}

            </ul>
            {% if interest.sub_entries %}
            <h5 class="child-item-header">Specific work or payments</h5>
            <div class="interest-child-items" id="parent-{{ interest.comparable_id }}">
                {% for child in interest.sub_entries %}
                    {{ entry_to_html(child) }}
                {% endfor %}
            </div>
            {% endif %}

        </div>

        """
)


def detail_to_html(detail: RegmemDetail) -> str:
    return detail_template.render(detail=detail, detail_to_html=detail_to_html)


def entry_to_html(entry: RegmemEntry) -> str:
    result = interest_template.render(
        interest=entry,
        detail_to_html=detail_to_html,
        entry_to_html=entry_to_html,
    )

    # remove blank lines
    result = "\n".join([x for x in result.split("\n") if x.strip()])

    # add new line at start and end
    result = f"\n{result}\n"

    return result


def convert_entry_to_legacy(entry: RegmemEntry) -> xml_interests.Item:
    text = entry_to_html(entry)
    content = MixedContentHolder(raw=text, text="")
    return xml_interests.Item(contents=content, **{"class": "interest"})


def convert_category_to_legacy(category: RegmemCategory) -> xml_interests.Category:
    return xml_interests.Category(
        type=category.category_id,
        name=category.category_name,
        records=[
            xml_interests.Record(
                items=[convert_entry_to_legacy(entry) for entry in category.entries]
            )
        ],
    )


def convert_person_to_legacy(person: RegmemPerson) -> xml_interests.PersonEntry:
    return xml_interests.PersonEntry(
        person_id=person.person_id,
        membername=person.person_name,
        date=person.published_date,
        record=None,
        categories=[
            convert_category_to_legacy(category) for category in person.categories
        ],
    )


def convert_legacy_to_entry(record: xml_interests.Item) -> RegmemEntry:
    return RegmemEntry(content=record.contents.raw, content_format="xml")


def convert_legacy_to_person(person: xml_interests.PersonEntry) -> RegmemPerson:
    categories = [
        RegmemCategory(
            category_id=category.type,
            category_name=category.name,
            entries=[
                convert_legacy_to_entry(record.items[0]) for record in category.records
            ],
        )
        for category in person.categories
    ]
    return RegmemPerson(
        chamber=Chamber.COMMONS,
        person_id=person.person_id,
        person_name=person.membername,
        categories=categories,
        published_date=person.date,
    )


def convert_register_to_legacy(regmem: RegmemRegister) -> xml_interests.Register:
    """
    Get the old-style xml format from the new-style json format.
    """
    return xml_interests.Register(
        tag="twfy",
        person_entries=[convert_person_to_legacy(person) for person in regmem.persons],
    )


def convert_legacy_to_register(
    legacy_register: xml_interests.Register,
    chamber: Chamber,
    published_date: datetime.date,
) -> RegmemRegister:
    """
    Create a new style json from the old style xml.
    """
    entries = [
        convert_legacy_to_person(person) for person in legacy_register.person_entries
    ]
    return RegmemRegister(
        chamber=chamber,
        published_date=published_date,
        persons=entries,
    )


def write_register_to_xml(
    register: RegmemRegister,
    *,
    xml_folder_name: str,
    force_refresh: bool = False,
):
    """
    Export a register to the old-style xml format.
    """
    dest_folder = parldata_path / "scrapedxml" / xml_folder_name

    if not dest_folder.exists():
        dest_folder.mkdir(exist_ok=True, parents=True)

    if not register.published_date:
        raise ValueError("Expects a global published_date")

    filename = f"regmem{register.published_date.isoformat()}.xml"

    dest = dest_folder / filename

    if not dest.exists() or force_refresh:
        legacy_register = convert_register_to_legacy(register)
        legacy_register.to_xml_path(dest)
