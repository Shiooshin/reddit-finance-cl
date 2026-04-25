"""Tests for get_config() env-var overrides."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import main.config as config_module


def _write_config(
    tmp_path: Path,
    *,
    openai_api_key: str,
) -> None:
    """Write a minimal valid config.json into tmp_path."""
    payload = {
        "reddit": {
            "subreddit": "finance_ukr",
            "post_limit": 1,
            "comment_limit": 1,
        },
        "openai": {
            "api_key": openai_api_key,
            "model": "gpt-4o",
            "max_tokens": 100,
        },
        "storage": {"db_path": "/tmp/insights.duckdb"},
        "logging": {"level": "INFO"},
    }
    (tmp_path / "config.json").write_text(json.dumps(payload))


@pytest.fixture(autouse=True)
def _reset_singleton() -> None:
    """get_config() caches the loaded Config — reset before each test."""
    config_module._config = None


def test_openai_api_key_falls_back_to_env_when_config_value_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_config(tmp_path, openai_api_key="")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-from-env")

    cfg = config_module.get_config()

    assert cfg.openai.api_key == "sk-from-env"


def test_config_value_takes_precedence_over_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_config(tmp_path, openai_api_key="sk-from-config")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-from-env")

    cfg = config_module.get_config()

    assert cfg.openai.api_key == "sk-from-config"


def test_api_key_stays_empty_when_neither_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_config(tmp_path, openai_api_key="")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    cfg = config_module.get_config()

    assert cfg.openai.api_key == ""
