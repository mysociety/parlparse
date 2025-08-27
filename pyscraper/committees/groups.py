import re
import unicodedata
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, RootModel, field_validator, model_validator


def slugify(value):
    """
    Converts to ASCII. Converts spaces to hyphens. Removes characters that
    aren't alphanumerics, underscores, or hyphens. Converts to lowercase.
    Also strips leading and trailing whitespace.
    """
    value = (
        unicodedata.normalize("NFKD", str(value))
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    value = re.sub(r"[^\w\s-]", "", value).strip().lower()
    return re.sub(r"[-\s]+", "-", value)


class MiniMember(BaseModel):
    name: str
    twfy_id: Optional[str]
    officer_role: Optional[str]
    external_member: bool = False
    is_current: bool = False


class MiniGroup(BaseModel):
    slug: str = ""
    name: str
    description: str
    external_url: str
    group_type: str
    group_categories: list[str] = Field(default_factory=list)
    members: list[MiniMember]

    @field_validator("name", mode="before")
    def set_name_slug(cls, v):
        if "committee" not in v.lower():
            return v.strip() + " Committee"
        return v

    @model_validator(mode="after")
    def set_slug_if_absent(self):
        if not self.slug:
            self.slug = slugify(self.name)
        return self


class MiniGroupCollection(RootModel[list[MiniGroup]]):
    @classmethod
    def from_path(cls, path: Path):
        with path.open("r") as f:
            data = f.read()
        return cls.model_validate_json(data)

    def to_path(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w") as f:
            f.write(self.model_dump_json(indent=2))
