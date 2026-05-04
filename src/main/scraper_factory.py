"""Scraper selection — lazy-imports the chosen implementation.

Lazy imports avoid loading optional dependencies (playwright, praw)
unless their corresponding scraper is selected via config.
"""

from __future__ import annotations

from typing import Protocol

from main.models import Post


class Scraper(Protocol):
    def fetch_posts(self) -> list[Post]: ...


def get_scraper(name: str) -> Scraper:
    """Instantiate the scraper named in config.

    Args:
        name: One of "rss", "playwright", "praw".

    Raises:
        ValueError: if name is not one of the known scrapers.
    """
    if name == "rss":
        from main.scraper_rss import RSSScraper
        return RSSScraper()
    if name == "playwright":
        from main.scraper_playwright import PlaywrightScraper
        return PlaywrightScraper()
    if name == "praw":
        from main.scraper import RedditScraper
        return RedditScraper()
    raise ValueError(f"Unknown scraper: {name!r}")
