from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    bluesky_username: str = Field(validation_alias="BLUESKY_USERNAME")
    bluesky_app_password: str = Field(validation_alias="BLUESKY_APP_PASSWORD")
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings(_env_file=".env", _env_file_encoding="utf-8")  # type: ignore
