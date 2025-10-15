from pathlib import Path
from typing import Optional

import spacy
from backports.strenum import StrEnum
from mysoc_validator import Transcript
from mysoc_validator.models.transcripts import SpeechItem
from pydantic import BaseModel, Field, RootModel
from spacy.cli import download
from typing_extensions import Self


class EntityType(StrEnum):
    POPOLO_PERSON = "POPOLO_PERSON"
    PERSON = "PERSON"
    LOCATION = "LOCATION"
    ORGANIZATION = "ORG"
    EVENT = "EVENT"
    LAW = "LAW"
    CONSTITUENCY = "CONSTITUENCY"
    GROUPS = "NORP"


class MatchType(StrEnum):
    WIKIPEDIA = "WIKIPEDIA"


class Entity(BaseModel):
    text: str
    label: EntityType


class AutoAnnotation(BaseModel):
    speech_id: str
    paragraph_pid: Optional[str] = None
    source_paragraph: str
    phrase: str
    entity_type: EntityType
    discarded: bool = False
    discard_reason: str = ""
    link: Optional[str] = None
    foreign_id: Optional[str] = None
    foreign_short_desc: Optional[str] = None
    foreign_long_desc: Optional[str] = None
    match_type: Optional[MatchType] = None


class AutoAnnotationList(RootModel):
    root: list[AutoAnnotation] = Field(default_factory=list)

    def __iter__(self):
        return iter(self.root)

    def __len__(self):
        return len(self.root)

    def active_count(self):
        return len([x for x in self.iter_active()])

    def iter_active(self):
        for item in self:
            if item.discarded is False:
                yield item

    def active_only(self):
        return AutoAnnotationList([x for x in self.iter_active()])

    def __getitem__(self, index):
        return self.root[index]

    def append(self, item: AutoAnnotation):
        self.root.append(item)

    def extend(self, items: Self):
        self.root.extend(items)

    @classmethod
    def from_path(cls, path: Path) -> Self:
        with path.open("r") as i:
            return cls.model_validate_json(i.read())

    def to_path(self, path: Path):
        with path.open("w") as o:
            o.write(self.model_dump_json(indent=2))


class SpeechNLP:
    def __init__(self):
        # Activate the NLP - if not present, download from spacy
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except OSError:
            download("en_core_web_sm")
            self.nlp = spacy.load("en_core_web_sm")

        self.allowed_labels = ["PERSON", "NORP", "ORG", "LAW", "EVENT"]

        # can extend this to pick up more things we know about, e.g. things from the popolo files
        ruler = self.nlp.add_pipe("entity_ruler", before="ner")
        patterns = [
            {"label": "ORG", "pattern": "Foreign, Commonwealth and Development Office"},
            {"label": "ORG", "pattern": "Department for Transport"},
        ]
        ruler.add_patterns(patterns)

    def extract_entities_from_text(self, text: str) -> list[Entity]:
        doc = self.nlp(text)
        entities = []
        for ent in doc.ents:
            if ent.label_ not in self.allowed_labels:
                continue
            entities.append(Entity(text=ent.text, label=EntityType(ent.label_)))
        return entities

    def extract_entities_from_speech_item(
        self, item: SpeechItem, speech_id: str
    ) -> AutoAnnotationList:
        entities = self.extract_entities_from_text(str(item))
        annotation_list = AutoAnnotationList()
        for e in entities:
            annotation_list.append(
                AutoAnnotation(
                    speech_id=speech_id,
                    paragraph_pid=item.pid,
                    source_paragraph=str(item),
                    phrase=e.text,
                    entity_type=e.label,
                )
            )
        return annotation_list

    def extract_entities_from_transcript(self, transcript: Transcript):
        annotations = AutoAnnotationList()
        for speech in transcript.iter_speeches():
            for item in speech.items:
                annotations.extend(
                    self.extract_entities_from_speech_item(item, speech.id)
                )
        return annotations
