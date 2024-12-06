from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Any, List, Optional

from jinja2 import Template
from pydantic import AliasChoices, AliasGenerator, BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


def multi_to_camel(value: str) -> AliasChoices:
    converted = to_camel(value)
    return AliasChoices(converted, value)


convert_config = ConfigDict(
    alias_generator=AliasGenerator(validation_alias=multi_to_camel)
)


field_template = Template(
    """
        <li class="interest-detail">
            <span class="interest-detail-name">{{ field.nice_name()|e  }}: </span>
            {% if field.value %}<span class="interest-detail-value">{{ field.value|e }}</span> {% endif %}
            {% if field.values %}
                <ul class="interest-detail-values-groups">
                {% for group in field.values %}
                    <li class="interest-detail-values-group">
                    {% for value in group %}
                        {{ value.to_html() }}
                    {% endfor %}
                    </li>
                {% endfor %}
                </ul>
            {% endif %}
        </li>
        """
)

interest_template = Template(
    """
        <p class="interest-summary">{{ interest.summary|e  }}</p>

        <ul class="interest-details-list">
        {% for field in interest.present_fields() %}
            {{field.to_html()}}
        {% endfor %}
            {% if interest.registration_date %}
            <li class="registration-date">Registration Date: {{ interest.registration_date.strftime('%d %B %Y') }}</li>
            {% endif %}
            {% if interest.published_date %}
            <li class="published-date">Published Date: {{ interest.published_date.strftime('%d %B %Y') }}</li>
            {% endif %}
            {% if interest.last_updated_date %}
            <li class="last-updated-date">Last Updated Date: {{ interest.last_updated_date.strftime('%d %B %Y') }}</li>
            {% endif %}

        </ul>

        """
)


class FieldModel(BaseModel):
    model_config = convert_config

    name: Optional[str] = None
    description: Optional[str] = None
    type: Optional[str] = None
    value: Optional[Any] = None
    values: Optional[List[List[FieldModel]]] = None

    def nice_name(self) -> str:
        """
        Convert from pascal case to a nice name.
        """
        if not self.name:
            return ""
        new_text = ""
        for char in self.name:
            if char.isupper():
                new_text += " "
            new_text += char
        return new_text.strip()

    def to_html(self, indent=0):
        return field_template.render(field=self)


class Link(BaseModel):
    model_config = convert_config

    rel: Optional[str] = Field(
        None, description="Relationship of the link to the object requested."
    )
    href: Optional[str] = Field(
        None, description="A complete URL that shows how the action can be performed."
    )
    method: Optional[str] = Field(None, description="Request method of the link.")


class Member(BaseModel):
    model_config = convert_config

    id: int = Field(description="ID of the member.")
    name_display_as: Optional[str] = Field(
        None,
        description="Member's current full name, as it should be displayed in text.",
    )
    name_list_as: Optional[str] = Field(
        None,
        description="Member's current name in the format {surname}, {forename}, for use in an ordered list.",
    )
    house: Optional[str] = Field(
        None,
        description="The name of the House the Member is currently associated with.",
    )
    member_from: Optional[str] = Field(
        None, description="Constituency of Commons Members."
    )
    party: Optional[str] = Field(
        None, description="Party the Member is currently associated with."
    )
    links: Optional[List[Link]] = Field(
        None,
        description="A list of HATEOAS Links for retrieving further information about this member.",
    )
    categories: List[PublishedCategory] = Field(default_factory=list)


class ProblemDetails(BaseModel):
    type: Optional[str] = None
    title: Optional[str] = None
    status: Optional[int] = None
    detail: Optional[str] = None
    instance: Optional[str] = None


class RegisterDocument(Enum):
    Full = "Full"
    Updated = "Updated"


class RegisterType(Enum):
    Commons = "Commons"


class PublishedCategory(BaseModel):
    model_config = convert_config

    id: int = Field(description="ID of the category.")
    number: str = Field(description="Number of the category in the code of conduct.")
    name: Optional[str] = Field(None, description="Name of the category.")
    type: Optional[RegisterType] = None
    links: Optional[List[Link]] = Field(
        None,
        description="A list of HATEOAS Links for retrieving further information about this category.",
    )
    interests: List[PublishedInterest] = Field(default_factory=list)


class PublishedInterest(BaseModel):
    model_config = convert_config

    id: int = Field(description="ID of the interest.")
    summary: str = Field(description="Title Summary for the interest.")
    parent_interest_id: Optional[int] = Field(
        None,
        description="The unique ID for the payer (parent interest) to which this payment (child interest) is associated.",
    )
    registration_date: Optional[date] = Field(
        None, description="Registration Date on the published interest."
    )
    published_date: Optional[date] = Field(
        None, description="Date when the interest was first published."
    )
    updated_date: List[date] = Field(
        default_factory=list,
        description="A list of dates on which the interest has been updated since it has been published.",
    )
    category: PublishedCategory
    member: Member
    fields: List[FieldModel] = Field(
        default_factory=list,
        description="List of fields which are available for a member to add further information about the interest.",
    )
    links: Optional[List[Link]] = Field(
        None,
        description="A list of HATEOAS Links for retrieving related information about this interest.",
    )
    child_items: list[PublishedInterest] = Field(default_factory=list)

    def present_fields(self) -> List[FieldModel]:
        return [x for x in self.fields if x.value or x.values]

    @property
    def last_updated_date(self) -> Optional[date]:
        if self.updated_date:
            return self.updated_date[-1]
        return None

    def to_html(self) -> str:
        result = interest_template.render(interest=self)

        # remove blank lines
        result = "\n".join([x for x in result.split("\n") if x.strip()])

        # add new line at start and end
        result = f"\n{result}\n"

        return result


class PublishedRegister(BaseModel):
    model_config = convert_config

    id: int = Field(description="ID of the register.")
    published_date: date = Field(description="Date when the Register was published.")
    type: Optional[RegisterType] = None
    links: Optional[List[Link]] = Field(
        None,
        description="A list of HATEOAS Links for retrieving related information about this register.",
    )
