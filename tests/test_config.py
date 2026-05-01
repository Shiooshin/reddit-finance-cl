"""Tests for config.get_config() env-var overrides."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from main import config as config_module


@pytest.fixture(autouse=True)
def _reset_config_singleton(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_config() caches in a module global; clear it between tests."""
    monkeypatch.setattr(config_module, "_config", None)


@pytest.fixture
def config_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Write a minimal config.json the loader can read, and point to it."""
    cfg = {
        "reddit": {
            "subreddit": "finance_ukr",
            "post_limit": 1,
            "comment_limit": 1,
            "client_id": "",
            "client_secret": "",
            "user_agent": "",
        },
        "openai": {
            "api_key": "FROM_FILE",
            "model": "gpt-4o",
            "max_tokens": 16,
        },
        "storage": {"db_path": "data/insights.duckdb"},
        "logging": {"level": "INFO"},
        "email": {
            "recipients": ["from-file@example.com"],
            "from_address": "sender@example.com",
            "aws_region": "eu-west-1",
            "subject_prefix": "[Reddit Insight]",
        },
    }
    path = tmp_path / "config.json"
    path.write_text(json.dumps(cfg))
    monkeypatch.setattr(config_module, "_CONFIG_PATH", path)
    return path


def test_openai_api_key_env_override_replaces_file_value(
    config_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "FROM_ENV")
    cfg = config_module.get_config()
    assert cfg.openai.api_key == "FROM_ENV"


def test_openai_api_key_unset_falls_back_to_file(
    config_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    cfg = config_module.get_config()
    assert cfg.openai.api_key == "FROM_FILE"


def test_openai_api_key_empty_env_falls_back_to_file(
    config_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "   ")
    cfg = config_module.get_config()
    assert cfg.openai.api_key == "FROM_FILE"


def test_openai_and_db_path_overrides_coexist(
    config_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "FROM_ENV")
    monkeypatch.setenv("DB_PATH", "/tmp/override.duckdb")
    cfg = config_module.get_config()
    assert cfg.openai.api_key == "FROM_ENV"
    assert cfg.storage.db_path == "/tmp/override.duckdb"


def test_email_recipients_loaded_from_file(
    config_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("EMAIL_RECIPIENTS", raising=False)
    cfg = config_module.get_config()
    assert cfg.email.recipients == ["from-file@example.com"]
    assert cfg.email.from_address == "sender@example.com"
    assert cfg.email.aws_region == "eu-west-1"
    assert cfg.email.subject_prefix == "[Reddit Insight]"


def test_email_recipients_env_override_replaces_file_value(
    config_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("EMAIL_RECIPIENTS", "a@x.com,b@x.com,  c@x.com  ")
    cfg = config_module.get_config()
    assert cfg.email.recipients == ["a@x.com", "b@x.com", "c@x.com"]


def test_email_recipients_empty_env_falls_back_to_file(
    config_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("EMAIL_RECIPIENTS", "   ")
    cfg = config_module.get_config()
    assert cfg.email.recipients == ["from-file@example.com"]
