from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def get_higher_path(folder_name: str) -> Path:
    current_level = Path.cwd()
    allowed_levels = 3
    for i in range(allowed_levels):
        if (current_level / folder_name).exists():
            return current_level / folder_name
        current_level = current_level.parent
    return Path.home() / folder_name


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
    parldata_path: Path = Field(default_factory=lambda: get_higher_path("parldata"))
    memberdata_path: Path = Field(default_factory=lambda: get_higher_path("members"))

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings(_env_file=".env", _env_file_encoding="utf-8")  # type: ignore
