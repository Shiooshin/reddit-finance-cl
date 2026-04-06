"""Project-wide logger factory."""

from __future__ import annotations

import logging
import sys

from main.config import Config


def get_logger(name: str) -> logging.Logger:
    """Return a named logger with a consistent format.

    Usage::

        from main.logger import get_logger
        log = get_logger(__name__)
        log.info("ready")
    """
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        logger.addHandler(handler)

    return logger


def configure_root() -> None:
    """Configure the root logger once at application startup.

    Level is read from ``Config.LOG_LEVEL`` (env var ``LOG_LEVEL``,
                                                  default ``INFO``).
    Call this from your entry point before anything else logs.
    """
    logging.basicConfig(
        level=Config.LOG_LEVEL,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )
