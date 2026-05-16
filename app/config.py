from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    telegram_bot_token: str = Field(default="")
    telegram_webhook_secret: str = Field(default="")
    telegram_allowed_user_ids: str = Field(default="")
    devin_api_key: str = Field(default="")
    devin_org_id: str = Field(default="")
    devin_default_session_id: str = Field(default="")
    data_dir: Path = Field(default=Path("data"))
    devin_base_url: str = Field(default="https://api.devin.ai/v3")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def allowed_user_ids(self) -> set[int]:
        ids: set[int] = set()
        for raw_user_id in self.telegram_allowed_user_ids.split(","):
            raw_user_id = raw_user_id.strip()
            if raw_user_id:
                ids.add(int(raw_user_id))
        return ids

    @property
    def sqlite_path(self) -> Path:
        return self.data_dir / "telegram-devin.db"


@lru_cache
def get_settings() -> Settings:
    return Settings()
