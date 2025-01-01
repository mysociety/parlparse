"""
This handles bi-directional conversions between the XML based regmem format and the new JSON based format.

We need to go in both directions because the XML format is still used for comparions over time.
"""

from __future__ import annotations

import datetime

from jinja2 import Template
from mysoc_validator.models import interests as legacy
from mysoc_validator.models.consts import Chamber
from mysoc_validator.models.xml_base import MixedContentHolder

from .funcs import parldata_path
from .models import (
    GenericRegmemCategory,
    GenericRegmemDetail,
    GenericRegmemEntry,
    GenericRegmemPerson,
    GenericRegmemRegister,
)

field_template = Template(
    """
        <li class="interest-detail">
            <span class="interest-detail-name">{{ field.name|e  }}: </span>
            {% if field.value %}<span class="interest-detail-value">{{ field.value|e }}</span> {% endif %}
            {% if field.subitems %}
                <ul class="interest-detail-values-groups">
                {% for value in group %}
                    {{ field_to_html(value) }}
                {% endfor %}
                </ul>
            {% endif %}
        </li>
        """
)

interest_template = Template(
    """
        <div class="interest-item" id="{{ interest.comparable_id }}">
        {% if interest.description %}
            {% if is_child %}
                <h6 class="interest-summary">{{ interest.description|e }}</h6>
            {% else %}
                <h4 class="interest-summary">{{ interest.description|e }}</h4>
            {% endif %}
        {% endif %}
            <ul class="interest-details-list">
            {% for field in interest.details %}
                {% if field.value or field.values %}
                    {{ field_to_html(field) }}
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

            </ul>
            {% if interest.child_items %}
            <h5 class="child-item-header">Specific work or payments</h5>
            <div class="interest-child-items" id="parent-{{ interest.comparable_id }}">
                {% for child in interest.child_items %}
                    {{ entry_to_html(child, is_child=True) }}
                {% endfor %}
            </div>
            {% endif %}

        </div>

        """
)


def field_to_html(field: GenericRegmemDetail) -> str:
    return field_template.render(field=field, field_to_html=field_to_html)


def entry_to_html(entry: GenericRegmemEntry, is_child: bool = False) -> str:
    result = interest_template.render(
        interest=entry,
        field_to_html=field_to_html,
        entry_to_html=entry_to_html,
        is_child=is_child,
    )

    # remove blank lines
    result = "\n".join([x for x in result.split("\n") if x.strip()])

    # add new line at start and end
    result = f"\n{result}\n"

    return result


def convert_entry_to_legacy(entry: GenericRegmemEntry) -> legacy.Item:
    text = entry_to_html(entry)
    content = MixedContentHolder(raw=text, text="")
    return legacy.Item(contents=content, **{"class": "interest"})


def convert_category_to_legacy(category: GenericRegmemCategory) -> legacy.Category:
    return legacy.Category(
        type=category.category_id,
        name=category.category_name,
        records=[
            legacy.Record(
                items=[convert_entry_to_legacy(entry) for entry in category.entries]
            )
        ],
    )


def convert_person_to_legacy(person: GenericRegmemPerson) -> legacy.PersonEntry:
    return legacy.PersonEntry(
        person_id=person.person_id,
        membername=person.person_name,
        date=person.published_date,
        record=None,
        categories=[
            convert_category_to_legacy(category) for category in person.categories
        ],
    )


def convert_legacy_to_entry(record: legacy.Item) -> GenericRegmemEntry:
    return GenericRegmemEntry(description=record.contents.raw, description_format="xml")


def convert_legacy_to_person(person: legacy.PersonEntry) -> GenericRegmemPerson:
    categories = [
        GenericRegmemCategory(
            category_id=category.type,
            category_name=category.name,
            entries=[
                convert_legacy_to_entry(record.items[0]) for record in category.records
            ],
        )
        for category in person.categories
    ]
    return GenericRegmemPerson(
        person_id=person.person_id,
        person_name=person.membername,
        categories=categories,
        published_date=person.date,
    )


def convert_register_to_legacy(regmem: GenericRegmemRegister) -> legacy.Register:
    """
    Get the old-style xml format from the new-style json format.
    """
    return legacy.Register(
        tag="twfy",
        person_entries=[convert_person_to_legacy(person) for person in regmem.entries],
    )


def convert_legacy_to_register(
    legacy_register: legacy.Register, chamber: Chamber, published_date: datetime.date
) -> GenericRegmemRegister:
    """
    Create a new style json from the old style xml.
    """
    entries = [
        convert_legacy_to_person(person) for person in legacy_register.person_entries
    ]
    return GenericRegmemRegister(
        chamber=chamber,
        published_date=published_date,
        entries=entries,
    )


def write_register_to_xml(
    register: GenericRegmemRegister,
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

    filename = f"regmem{register.published_date.isoformat()}.xml"

    dest = dest_folder / filename

    if not dest.exists() or force_refresh:
        legacy_register = convert_register_to_legacy(register)
        legacy_register.to_xml_path(dest)
