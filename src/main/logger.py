"""Project-wide logger factory."""

from __future__ import annotations

import logging
import sys


def get_logger(name: str) -> logging.Logger:
    """Return a named logger. Output handler is owned by root (see configure_root)."""
    return logging.getLogger(name)


def configure_root(level: str = "INFO") -> None:
    """Configure the root logger once at application startup."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )
