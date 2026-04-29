"""File-based configuration loaded from config.json."""

from __future__ import annotations

import json
import os
from pathlib import Path

from pydantic import BaseModel

_CONFIG_PATH = Path("config.json")


class RedditConfig(BaseModel):
    subreddit: str
    post_limit: int
    comment_limit: int
    # PRAW-only — not used by PlaywrightScraper
    client_id: str = ""
    client_secret: str = ""
    user_agent: str = ""


class OpenAIConfig(BaseModel):
    api_key: str
    model: str
    max_tokens: int


class StorageConfig(BaseModel):
    db_path: str


class LoggingConfig(BaseModel):
    level: str


class Config(BaseModel):
    reddit: RedditConfig
    openai: OpenAIConfig
    storage: StorageConfig
    logging: LoggingConfig

    @classmethod
    def load(cls, path: Path = _CONFIG_PATH) -> Config:
        with open(path) as f:
            return cls.model_validate(json.load(f))


_config: Config | None = None


def get_config() -> Config:
    """Return the singleton Config, loading config.json on first call.

    Environment variable overrides applied after load:
      - DB_PATH        overrides storage.db_path
      - OPENAI_API_KEY overrides openai.api_key
    """
    global _config
    if _config is None:
        _config = Config.load(_CONFIG_PATH)

        db_path = os.environ.get("DB_PATH", "").strip()
        if db_path:
            _config = _config.model_copy(
                update={"storage": StorageConfig(db_path=db_path)}
            )

        api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if api_key:
            new_openai = _config.openai.model_copy(update={"api_key": api_key})
            _config = _config.model_copy(update={"openai": new_openai})

    return _config
