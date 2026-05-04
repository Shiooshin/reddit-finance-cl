"""Reddit scraper — fetches posts and comments via public RSS feeds.

Reddit blocks JSON endpoints from datacenter egress (e.g. AWS Fargate)
without OAuth, but allows public Atom feeds. This scraper uses
feedparser against /r/<sub>/top/.rss for listings and
/r/<sub>/comments/<post_id>/.rss for per-post comments.

Failure semantics:
  - Listing fetch failure (HTTP != 200 or empty entries) raises and
    fails the run. ECS task exits non-zero.
  - Per-post comment fetch failure logs a warning and returns an empty
    comment list; the post is still kept.

Comments are sorted by recency (RSS sort=new), not by score. The
comment_limit slices the first N entries from the feed.
"""

from __future__ import annotations

from datetime import UTC, datetime
from time import mktime
from typing import Any

import feedparser  # type: ignore[import-not-found]

from main.config import get_config
from main.logger import get_logger
from main.models import Comment, Post

log = get_logger(__name__)

_BASE_URL = "https://www.reddit.com"
_USER_AGENT = "reddit-insight-engine/0.1"
_T3_PREFIX = "tag:reddit.com,2008:t3_"


class RSSScraper:
    """Fetches posts and comments from a subreddit via Reddit Atom feeds."""

    def __init__(self) -> None:
        self._cfg = get_config().reddit

    def fetch_posts(self) -> list[Post]:
        sub = self._cfg.subreddit
        post_limit = self._cfg.post_limit

        log.info("Fetching top %d posts from r/%s via RSS", post_limit, sub)
        feed = self._fetch_listing(sub)
        entries = feed.entries[:post_limit]

        posts: list[Post] = []
        for entry in entries:
            raw_id = getattr(entry, "id", "")
            post_id = _extract_post_id(raw_id)
            if not post_id:
                log.warning("Skipping entry with no parseable id: %r", raw_id)
                continue
            comments = self._fetch_comments(sub, post_id)
            posts.append(_build_post(entry, post_id, comments))
            log.debug(
                "Post %s | comments=%d | %r",
                post_id, len(comments), getattr(entry, "title", ""),
            )

        log.info("Fetched %d posts from r/%s", len(posts), sub)
        return posts

    def _fetch_listing(self, sub: str) -> Any:
        url = f"{_BASE_URL}/r/{sub}/top/.rss?t=day"
        feed = feedparser.parse(url, agent=_USER_AGENT)
        status = getattr(feed, "status", 0)
        if status != 200:
            raise RuntimeError(
                f"Listing fetch failed: HTTP {status} for {url}"
            )
        if not feed.entries:
            raise RuntimeError(f"Listing returned no entries: {url}")
        return feed

    def _fetch_comments(self, sub: str, post_id: str) -> list[Comment]:
        limit = self._cfg.comment_limit
        url = f"{_BASE_URL}/r/{sub}/comments/{post_id}/.rss"
        try:
            feed = feedparser.parse(url, agent=_USER_AGENT)
            status = getattr(feed, "status", 0)
            if status != 200:
                log.warning(
                    "Comment fetch HTTP %s for post %s — empty comments",
                    status, post_id,
                )
                return []
            real_entries = [
                e for e in feed.entries
                if "t3_" not in getattr(e, "id", "")
            ]
            return [_build_comment(e, post_id) for e in real_entries[:limit]]
        except Exception as exc:
            log.warning("Comment fetch failed for post %s: %s", post_id, exc)
            return []


# --- Helpers ---


def _extract_id(raw_id: str, marker: str) -> str:
    """Extract a bare Reddit ID from various Atom <id> formats.

    Handles both the tag URI format (tag:reddit.com,2008:<marker><id>)
    and the URL format (https://...<marker><id>).

    ``marker`` is the type prefix without the trailing id, e.g. ``"t3_"``
    for posts and ``"t1_"`` for comments.
    """
    # Atom tag URI: tag:reddit.com,2008:<marker><id>
    tag_prefix = f"tag:reddit.com,2008:{marker}"
    if raw_id.startswith(tag_prefix):
        return raw_id[len(tag_prefix):]
    # URL format: ...<marker><id>
    idx = raw_id.find(marker)
    if idx != -1:
        return raw_id[idx + len(marker):]
    return ""


def _extract_post_id(raw_id: str) -> str:
    return _extract_id(raw_id, "t3_")


def _parse_datetime(entry: Any) -> datetime:
    parsed = (
        getattr(entry, "published_parsed", None)
        or getattr(entry, "updated_parsed", None)
    )
    if parsed is None:
        return datetime.now(tz=UTC)
    return datetime.fromtimestamp(mktime(parsed), tz=UTC)


def _parse_author(entry: Any) -> str:
    raw = getattr(entry, "author", "") or ""
    return raw.removeprefix("/u/") or "[deleted]"


def _selftext(entry: Any) -> str:
    content = getattr(entry, "content", None)
    if content and len(content) > 0:
        return content[0].get("value", "") or ""
    return getattr(entry, "summary", "") or ""


def _build_post(entry: Any, post_id: str, comments: list[Comment]) -> Post:
    return Post(
        id=post_id,
        title=getattr(entry, "title", ""),
        selftext=_selftext(entry),
        author=_parse_author(entry),
        created_at=_parse_datetime(entry),
        url=getattr(entry, "link", ""),
        comments=comments,
    )


def _build_comment(entry: Any, post_id: str) -> Comment:
    return Comment(
        id=_extract_id(getattr(entry, "id", ""), "t1_"),
        post_id=post_id,
        body=_selftext(entry),
        author=_parse_author(entry),
        created_at=_parse_datetime(entry),
    )
