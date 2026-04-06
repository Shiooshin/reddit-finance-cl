"""File-based configuration loaded from config.json."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

_CONFIG_PATH = Path("config.json")


class RedditConfig(BaseModel):
    client_id: str
    client_secret: str
    user_agent: str
    subreddit: str
    post_limit: int
    comment_limit: int


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
    """Return the singleton Config instance, loading config.json on first call."""
    global _config
    if _config is None:
        _config = Config.load()
    return _config
