"""Runtime configuration shared by api + worker.

DATABASE_URL and REDIS_URL come from the environment (docker compose sets them
from the .env on the box). Local development should mirror via .env in CWD.
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = Field(
        default="postgresql://curb:curb@localhost:5432/curb",
        alias="DATABASE_URL",
    )
    redis_url: str = Field(default="redis://localhost:6379", alias="REDIS_URL")
    model_provider: str = Field(default="google-gla", alias="MODEL_PROVIDER")
    model_api_key: str = Field(default="", alias="MODEL_API_KEY")


def load_settings() -> Settings:
    return Settings()
