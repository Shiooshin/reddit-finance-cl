"""Pipeline — orchestrates the full scrape → process → analyze flow."""

from __future__ import annotations

from main.analyzer import Analyzer
from main.logger import get_logger
from main.models import AnalysisResult
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
        """Execute the full pipeline: scrape → store → analyze new → print."""
        log.info("Pipeline started")

        log.info("Step 1/3 — scraping posts")
        posts = self.scraper.fetch_posts()
        log.info("Fetched %d posts", len(posts))

        log.info("Step 2/3 — storing raw posts")
        for post in posts:
            self.storage.save_post(post)

        unanalyzed = self.storage.get_unanalyzed_posts()
        if not unanalyzed:
            log.info("No new posts to analyze")
            return
        log.info("%d new posts to analyze", len(unanalyzed))

        log.info("Step 3/3 — processing and analyzing posts")
        results = self.processor.process(unanalyzed, self.analyzer)

        for result in results:
            self.storage.save_analysis(result)

        log.info("Pipeline complete — %d posts analyzed", len(results))
        self._print_results(results)

    def _print_results(self, results: list[AnalysisResult]) -> None:
        for result in results:
            print(f"\n{'=' * 60}")
            print(f"Post:      {result.post_id}")
            print(
                f"Sentiment: {result.sentiment}"
                f" (confidence: {result.confidence_score}/100)"
            )
            print(f"Summary:   {result.summary}")
            if result.key_topics:
                print(f"Topics:    {', '.join(result.key_topics)}")
            if result.pain_points:
                print("Pain points:")
                for point in result.pain_points:
                    print(f"  - {point}")
            if result.opportunities:
                print("Opportunities:")
                for opp in result.opportunities:
                    print(
                        f"  [{opp.type}] {opp.description}"
                        f" (risk={opp.risk_level}, horizon={opp.time_horizon})"
                    )
            if result.contrarian_insights:
                print("Contrarian:")
                for insight in result.contrarian_insights:
                    print(f"  - {insight}")
        print(f"\n{'=' * 60}")
