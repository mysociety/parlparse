from __future__ import annotations

from dataclasses import dataclass
from hashlib import md5
from pathlib import Path
from typing import ClassVar, TypeVar

import jsonref
from backports.strenum import StrEnum
from huggingface_hub import AsyncInferenceClient
from pydantic import BaseModel, Field, RootModel
from pydantic_ai import Agent
from pydantic_ai.models.huggingface import HuggingFaceModel
from pydantic_ai.profiles import ModelProfile
from pydantic_ai.profiles._json_schema import JsonSchemaTransformer
from pydantic_ai.providers.huggingface import HuggingFaceProvider

from ..settings import settings

T = TypeVar("T", bound=BaseModel)


@dataclass(init=False)
class ExpandedSchemaTransformer(JsonSchemaTransformer):
    def transform(self, schema):
        return schema

    def walk(self):
        schema = super().walk()
        items = jsonref.replace_refs(schema, proxies=False, jsonschema=True)
        # delete "$defs" if it exists
        if "$defs" in items:  # type: ignore
            del items["$defs"]  # type: ignore
        return items


hf_endpoint_model = HuggingFaceModel(
    model_name="olmo-2-1124-7b-instruct",  # nothing uses this this, but for the record
    profile=ModelProfile(
        json_schema_transformer=ExpandedSchemaTransformer,
    ),
    provider=HuggingFaceProvider(
        hf_client=AsyncInferenceClient(
            api_key=settings.hf_token, model=settings.hf_inference_endpoint
        )
    ),
)


class AgentCache(RootModel[T]):
    root: dict[str, T] = Field(default_factory=dict)
    storage_path: ClassVar[Path] = Path(
        settings.parldata_path / "wikilinks" / "relevance_cache.json"
    )

    @classmethod
    def load(cls):
        if cls.storage_path.exists():
            with cls.storage_path.open("r") as f:
                return cls.model_validate_json(f.read())
        return cls()

    def save(self) -> None:
        path = self.__class__.storage_path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            f.write(self.model_dump_json(indent=2))

    @staticmethod
    def hash_value(long_key: str) -> str:
        return md5(long_key.encode("utf-8")).hexdigest()

    def __getitem__(self, long_key: str) -> T | None:
        short_key = self.__class__.hash_value(long_key)
        return self.root.get(short_key)

    def __setitem__(self, long_key: str, value: T) -> None:
        short_key = self.__class__.hash_value(long_key)
        self.root[short_key] = value
        self.save()


class LinkClassification(StrEnum):
    valid_link = "valid_link"
    wrong_article = "wrong_article"
    article_too_general = "article_too_general"


class ComboLinkReason(BaseModel):
    explanation: str = Field(
        description="A one sentence explaination of why the link is correct or not."
    )
    link_status: LinkClassification = Field(
        description="The classification of the link in context."
    )


class LinkRelevance(BaseModel):
    explanation: str = Field(
        description="A one sentence explaination of why the link is correct or not."
    )
    link_irrelevant: bool = Field(description="If link is not relevant to context")


class LinkTooGeneral(BaseModel):
    explanation: str = Field(
        description="A one sentence explaination of why the link is correct or not."
    )
    link_too_general: bool = Field(description="Link is too general to highlight")


def combined_wikipedia_check(
    paragraph: str, title: str, desc: str, override_cache: bool = False
) -> ComboLinkReason:
    too_general = check_wikipedia_too_abstract(paragraph, title, desc, override_cache)
    if too_general.link_too_general is True:
        return ComboLinkReason(
            explanation=too_general.explanation,
            link_status=LinkClassification.article_too_general,
        )

    relevance = check_wikipedia_relevance(paragraph, title, desc, override_cache)
    if relevance.link_irrelevant is True:
        return ComboLinkReason(
            explanation=relevance.explanation,
            link_status=LinkClassification.wrong_article,
        )

    return ComboLinkReason(explanation="", link_status=LinkClassification.valid_link)


def check_wikipedia_relevance(
    paragraph: str, title: str, desc: str, override_cache: bool = False
) -> LinkRelevance:
    prompt = f"""
    You are a checker of links from a UK parliamentary proceedings to Wikipedia articles.
    We are using this to help give greater context to what is being discussed in the debate.
    You are given a paragraph from a debate, and then a proposed link to a Wikipedia article.
    This may be about a person mentioned (inside or outside the parliament), an organisation, or an event.

    You must decide if the link makes sense in the context of the paragraph, or if this is a 
    false positive based on name alone.

    Pay attention to where the highlighted phrase is only part of a larger phrase in context - this is often a sign of a false positive.

    Paragraph:

    {paragraph}

    Link:

    {title} - {desc}
    """

    agent = Agent(model=hf_endpoint_model, output_type=LinkRelevance)

    result = agent.run_sync(prompt).output
    return result


def check_wikipedia_too_abstract(
    paragraph: str, title: str, desc: str, override_cache: bool = False
) -> LinkTooGeneral:
    prompt = f"""
    You are a checker of links from a UK parliamentary proceedings to Wikipedia articles.
    We are using this to help give greater context to what is being discussed in the debate.
    You are given a paragraph from a debate, and then a proposed link to a Wikipedia article.
    This may be about a person mentioned (inside or outside the parliament), an organisation, or an event.

    Wikipedia contains a lot of very general articles that are not useful for this purpose. 
    e.g. ones flagging very general concepts like 'economics', 'government', that are unlikely to enhance the 
    understanding of the debate.

    We want links that are specific to what is being mentioned. Flag ones that are not. 

    Paragraph:

    {paragraph}

    Link:

    {title} - {desc}
    """

    agent = Agent(model=hf_endpoint_model, output_type=LinkTooGeneral)

    result = agent.run_sync(prompt).output
    return result
