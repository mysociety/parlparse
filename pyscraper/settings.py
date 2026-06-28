from pathlib import Path
from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def get_higher_path(folder_name: str, alt_names: Optional[List[str]] = None) -> Path:
    current_level = Path.cwd()
    names_to_check = [folder_name] + (alt_names or [])
    allowed_levels = 3
    for i in range(allowed_levels):
        for name in names_to_check:
            if (current_level / name).exists():
                return current_level / name
        current_level = current_level.parent
    return Path.home() / folder_name


memberdata_path = get_higher_path("members")


class Settings(BaseSettings):
    bluesky_username: Optional[str] = Field(
        default=None, validation_alias="BLUESKY_USERNAME"
    )
    bluesky_app_password: Optional[str] = Field(
        default=None, validation_alias="BLUESKY_APP_PASSWORD"
    )
    hf_token: Optional[str] = Field(default=None, validation_alias="HUGGINGFACE_TOKEN")
    hf_inference_endpoint: Optional[str] = Field(
        default=None, validation_alias="HUGGINGFACE_INFERENCE_ENDPOINT"
    )
    parldata_path: Path = Field(
        default_factory=lambda: get_higher_path("parldata", alt_names=["pwdata"])
    )
    memberdata_path: Path = Field(default_factory=lambda: get_higher_path("members"))

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings(_env_file=".env", _env_file_encoding="utf-8")  # type: ignore
