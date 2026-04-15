"""Pipeline — orchestrates the full scrape → store → analyze → print flow."""

from __future__ import annotations

from main.analyzer import Analyzer
from main.logger import get_logger
from main.print_writer import PrintWriter
from main.processor import Processor
from main.scraper import RedditScraper

log = get_logger(__name__)


class Pipeline:
    """Wires all modules together and defines execution order."""

    def __init__(self) -> None:
        self.scraper = RedditScraper()
        self.processor = Processor()
        self.analyzer = Analyzer()
        self.writer = PrintWriter()  # DuckDBWriter()

    def run(self) -> None:
        """Execute the full pipeline: scrape → store → analyze new → print."""
        log.info("Pipeline started")

        log.info("Step 1/3 — scraping posts")
        posts = self.scraper.fetch_posts()
        log.info("Fetched %d posts", len(posts))
        
        if not posts:
            log.info("No new posts to analyze")
            return
        log.info("%d new posts to analyze", len(posts))

        log.info("Step 2/3 — storing raw posts")
        self.writer.write_raw_posts(posts)

        log.info("Step 3/3 — processing and analyzing posts")
        results = self.processor.process(posts, self.analyzer)

        # self.writer.write_analytical_results(results)
        self.writer.write_analytical_results(results)

        log.info("Pipeline complete — %d posts analyzed", len(results))
