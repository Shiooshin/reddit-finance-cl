#!/usr/bin/env python3
"""Entry point — run the Reddit Insight Engine pipeline."""

from main.config import get_config
from main.logger import configure_root
from main.pipeline import Pipeline

if __name__ == "__main__":
    config = get_config()
    configure_root(level=config.logging.level)
    Pipeline().run()
