"""Pipeline — orchestrates the full scrape → process → analyze flow."""

from __future__ import annotations

from main.analyzer import Analyzer
from main.logger import get_logger
from main.processor import Processor
from main.scraper import RedditScraper
from main.storage import Storage

log = get_logger(__name__)


class Pipeline:
    """Wires all modules together and defines execution order."""

    def __init__(self) -> None:
        self.scraper = RedditScraper()
        self.storage = Storage()
        self.processor = Processor()
        self.analyzer = Analyzer()

    def run(self) -> None:
        """Execute the full pipeline end-to-end."""
        pass
