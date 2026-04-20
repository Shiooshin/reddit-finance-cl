"""Reddit scraper — fetches posts and comments via Playwright."""

from __future__ import annotations

import asyncio
import random
from datetime import UTC, datetime
from typing import Any

from playwright.async_api import BrowserContext, async_playwright
from tenacity import retry, stop_after_attempt, wait_exponential

from main.config import get_config
from main.logger import get_logger
from main.models import Comment, Post

log = get_logger(__name__)

_BASE_URL = "https://www.reddit.com"

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)

_HEADERS = {
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "application/json, text/plain, */*",
}


async def _delay(lo: float = 1.0, hi: float = 3.0) -> None:
    """Random sleep to mimic human pacing and avoid rate-limit triggers."""
    await asyncio.sleep(random.uniform(lo, hi))


class PlaywrightScraper:
    """Fetches posts and comments from a subreddit via Reddit's JSON API.

    Uses a Playwright browser context for user-agent and session management,
    but calls Reddit's public .json endpoints directly rather than intercepting
    the browser-rendered page (Reddit's redesign no longer calls top.json).
    Post and comment limits are read from config.json.
    """

    def __init__(self) -> None:
        self._cfg = get_config().reddit

    def fetch_posts(self) -> list[Post]:
        """Fetch today's top posts from the configured subreddit."""
        return asyncio.run(self._run())

    # ------------------------------------------------------------------ #
    # Internal async implementation
    # ------------------------------------------------------------------ #

    async def _run(self) -> list[Post]:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=_USER_AGENT,
                viewport={"width": 1920, "height": 1080},
                locale="en-US",
                timezone_id="America/New_York",
                extra_http_headers=_HEADERS,
            )
            try:
                return await self._scrape(context)
            finally:
                await browser.close()

    async def _scrape(self, context: BrowserContext) -> list[Post]:
        raw_posts = await self._fetch_listing(context)
        log.info(
            "Collected %d raw posts from r/%s",
            len(raw_posts),
            self._cfg.subreddit,
        )

        posts: list[Post] = []
        for raw in raw_posts:
            post_id = raw.get("id", "")
            await _delay(0.5, 1.5)
            comments = await self._fetch_comments(context, post_id)
            posts.append(_build_post(raw, comments))
            log.debug(
                "Post %s | score=%d | comments=%d | %r",
                post_id,
                raw.get("score", 0),
                len(comments),
                raw.get("title", ""),
            )

        log.info("Fetched %d posts from r/%s", len(posts), self._cfg.subreddit)
        return posts

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def _fetch_listing(
        self, context: BrowserContext
    ) -> list[dict[str, Any]]:
        """Fetch posts directly from Reddit's JSON listing API.

        Paginates via the 'after' token until post_limit is reached.
        """
        subreddit = self._cfg.subreddit
        post_limit = self._cfg.post_limit
        collected: list[dict[str, Any]] = []
        after: str | None = None

        while len(collected) < post_limit:
            url = (
                f"{_BASE_URL}/r/{subreddit}/top.json"
                f"?t=day&limit=100&raw_json=1"
            )
            if after:
                url += f"&after={after}"

            log.info("Fetching listing page: %s", url)
            response = await context.request.get(url)

            if not response.ok:
                log.warning(
                    "Listing request failed: HTTP %d for %s",
                    response.status,
                    url,
                )
                break

            data = await response.json()
            children = data.get("data", {}).get("children", [])
            for child in children:
                if child.get("kind") == "t3":
                    d = child.get("data", {})
                    if d.get("id"):
                        collected.append(d)

            after = data.get("data", {}).get("after")
            if not after or not children:
                break

            await _delay(1.0, 2.0)

        log.info("Listing collected %d posts", len(collected))
        return collected[:post_limit]

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=8),
        reraise=True,
    )
    async def _fetch_comments(
        self, context: BrowserContext, post_id: str
    ) -> list[Comment]:
        """Fetch top comments for a post via Reddit's JSON API."""
        limit = self._cfg.comment_limit
        url = (
            f"{_BASE_URL}/comments/{post_id}/.json"
            f"?sort=top&limit={limit}&raw_json=1"
        )

        comments: list[Comment] = []
        try:
            response = await context.request.get(url)
            if not response.ok:
                log.warning(
                    "Comments request failed for post %s: HTTP %d",
                    post_id,
                    response.status,
                )
                return comments

            body = await response.json()
            # Reddit returns [post_listing, comment_listing]
            if isinstance(body, list) and len(body) > 1:
                children = body[1].get("data", {}).get("children", [])
                for child in children:
                    if child.get("kind") != "t1":
                        continue
                    d = child["data"]
                    body_text = d.get("body", "")
                    if body_text in ("", "[deleted]", "[removed]"):
                        continue
                    comments.append(Comment(
                        id=d.get("id", ""),
                        post_id=post_id,
                        body=body_text,
                        author=d.get("author") or "[deleted]",
                        score=d.get("score", 0),
                        created_at=datetime.fromtimestamp(
                            d.get("created_utc", 0), tz=UTC
                        ),
                    ))
        except Exception as exc:
            log.warning(
                "Failed to fetch comments for post %s: %s", post_id, exc
            )

        top = sorted(comments, key=lambda c: c.score, reverse=True)[:limit]
        log.debug("Post %s: %d comments fetched", post_id, len(top))
        return top


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

def _build_post(raw: dict[str, Any], comments: list[Comment]) -> Post:
    return Post(
        id=raw.get("id", ""),
        title=raw.get("title", ""),
        selftext=raw.get("selftext", ""),
        author=raw.get("author") or "[deleted]",
        score=raw.get("score", 0),
        num_comments=raw.get("num_comments", 0),
        created_at=datetime.fromtimestamp(
            raw.get("created_utc", 0), tz=UTC
        ),
        url=raw.get("url", ""),
        comments=comments,
    )
