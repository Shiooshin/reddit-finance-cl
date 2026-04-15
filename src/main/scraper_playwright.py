"""Reddit scraper — fetches posts and comments via Playwright."""

from __future__ import annotations

import asyncio
import random
from datetime import datetime, timezone
from typing import Any

from playwright.async_api import BrowserContext, Page, async_playwright
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
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,*/*;q=0.8"
    ),
}


async def _delay(lo: float = 1.0, hi: float = 3.0) -> None:
    """Random sleep to mimic human pacing and avoid rate-limit triggers."""
    await asyncio.sleep(random.uniform(lo, hi))


class PlaywrightScraper:
    """Fetches posts and comments from a subreddit using a headless browser.

    Navigates the real Reddit page and intercepts the internal JSON API
    calls it makes — no HTML parsing, no API credentials required.
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
            # Drop ad/tracking requests to reduce noise and detection surface
            await context.route(
                "**/{ads,tracking,telemetry,analytics}/**",
                lambda route, _: route.abort(),
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
            await _delay(1.0, 2.5)  # rate limiting between post fetches
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
        """Navigate the subreddit page and intercept JSON listing responses."""
        collected: list[dict[str, Any]] = []
        page = await context.new_page()

        async def handle(route, _request):  # type: ignore[no-untyped-def]
            response = await route.fetch()
            try:
                body = await response.json()
                children = body.get("data", {}).get("children", [])
                collected.extend(
                    c["data"]
                    for c in children
                    if c.get("kind") == "t3"
                    and c.get("data", {}).get("id")
                )
            except Exception:
                pass
            await route.fulfill(response=response)

        subreddit = self._cfg.subreddit
        post_limit = self._cfg.post_limit

        await page.route(f"**/{subreddit}/top.json**", handle)

        url = f"{_BASE_URL}/r/{subreddit}/top/?t=day"
        log.info("Loading %s", url)
        await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        await _delay(1.5, 3.0)

        # Scroll to trigger dynamic loading until we have enough posts
        max_scrolls = max(5, (post_limit // 25) + 3)
        for attempt in range(max_scrolls):
            if len(collected) >= post_limit:
                break
            await _scroll_to_bottom(page)
            await _delay(1.5, 3.0)
            log.debug(
                "Scroll %d/%d — %d posts collected",
                attempt + 1,
                max_scrolls,
                len(collected),
            )

        await page.close()
        return collected[:post_limit]

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=8),
        reraise=True,
    )
    async def _fetch_comments(
        self, context: BrowserContext, post_id: str
    ) -> list[Comment]:
        """Fetch top comments for a post by intercepting its JSON endpoint."""
        comments: list[Comment] = []
        page = await context.new_page()

        async def handle(route, _request):  # type: ignore[no-untyped-def]
            response = await route.fetch()
            try:
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
                                d.get("created_utc", 0), tz=timezone.utc
                            ),
                        ))
            except Exception:
                pass
            await route.fulfill(response=response)

        limit = self._cfg.comment_limit
        url = (
            f"{_BASE_URL}/comments/{post_id}/.json"
            f"?sort=top&limit={limit}"
        )

        try:
            await page.route("**/.json**", handle)
            await page.goto(url, wait_until="domcontentloaded", timeout=20_000)
            await _delay(0.5, 1.5)
        except Exception as exc:
            log.warning(
                "Failed to fetch comments for post %s: %s", post_id, exc
            )
        finally:
            await page.close()

        top = sorted(comments, key=lambda c: c.score, reverse=True)[:limit]
        log.debug("Post %s: %d comments fetched", post_id, len(top))
        return top


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

async def _scroll_to_bottom(page: Page) -> None:
    """Scroll to the bottom of the page to trigger dynamic content loading."""
    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")


def _build_post(raw: dict[str, Any], comments: list[Comment]) -> Post:
    return Post(
        id=raw.get("id", ""),
        title=raw.get("title", ""),
        selftext=raw.get("selftext", ""),
        author=raw.get("author") or "[deleted]",
        score=raw.get("score", 0),
        num_comments=raw.get("num_comments", 0),
        created_at=datetime.fromtimestamp(
            raw.get("created_utc", 0), tz=timezone.utc
        ),
        url=raw.get("url", ""),
        comments=comments,
    )
