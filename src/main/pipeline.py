"""Pipeline — orchestrates the full scrape → store → analyze → notify flow."""

from __future__ import annotations

from main.analyzer import Analyzer
from main.duckdb_writer import DuckDBWriter
from main.email_notifier import EmailNotifier
from main.logger import get_logger
from main.processor import Processor
from main.scraper_playwright import PlaywrightScraper

log = get_logger(__name__)


class Pipeline:
    """Wires all modules together and defines execution order."""

    def __init__(self) -> None:
        self.scraper = PlaywrightScraper()
        self.processor = Processor()
        self.analyzer = Analyzer()
        self.writer: DuckDBWriter = DuckDBWriter()
        self.notifier = EmailNotifier()

    def run(self) -> None:
        """Execute the full pipeline: scrape → dedupe → store → analyze → notify."""
        log.info("Pipeline started")

        log.info("Step 1/3 — scraping posts")
        posts = self.scraper.fetch_posts()
        log.info("Fetched %d posts", len(posts))

        if not posts:
            log.info("No posts returned from scraper")
            return

        new_posts = [p for p in posts if not self.writer.post_exists(p.id)]
        log.info(
            "%d new posts to process (skipping %d already stored)",
            len(new_posts),
            len(posts) - len(new_posts),
        )

        if not new_posts:
            log.info("No new posts to analyze")
            return

        log.info("Step 2/3 — storing raw posts")
        self.writer.write_raw_posts(new_posts)

        log.info("Step 3/3 — processing and analyzing posts")
        pairs = self.processor.process(new_posts, self.analyzer)
        results = [r for _, r in pairs]
        self.writer.write_analytical_results(results)

        try:
            self.notifier.send_digest(pairs)
        except Exception:
            log.exception("Email notification failed; pipeline continues")

        log.info("Pipeline complete — %d posts analyzed", len(pairs))
