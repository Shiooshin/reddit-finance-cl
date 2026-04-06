"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os


class Config:
    """Central config object. Reads from environment / .env at startup."""

    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # Add project-specific settings below.
    # DATABASE_URL: str = os.environ["DATABASE_URL"]
