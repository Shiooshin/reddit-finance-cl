"""Reddit scraper — fetches posts and comments via PRAW."""

from __future__ import annotations

import os
from datetime import datetime, timezone

import praw
import praw.models

from main.config import get_config
from main.logger import get_logger
from main.models import Comment, Post

log = get_logger(__name__)


class RedditScraper:
    """Fetches posts and comment trees from a subreddit using PRAW.

    Credentials are read from environment variables:
        REDDIT_CLIENT_ID
        REDDIT_CLIENT_SECRET
        REDDIT_USER_AGENT  (optional, defaults to 'reddit-insight-engine/0.1')

    Post and comment limits are read from config.json.
    """

    def __init__(self) -> None:
        self._config = get_config()
        self._reddit = praw.Reddit(
            client_id=os.environ["REDDIT_CLIENT_ID"],
            client_secret=os.environ["REDDIT_CLIENT_SECRET"],
            user_agent=os.environ.get("REDDIT_USER_AGENT", "reddit-insight-engine/0.1"),
        )
        log.info("Reddit client initialized (read-only: %s)", self._reddit.read_only)

    def fetch_posts(self) -> list[Post]:
        """Fetch today's top posts from the configured subreddit.

        Returns:
            List of Post objects, each with top comments attached.
        """
        subreddit = self._config.reddit.subreddit
        limit = self._config.reddit.post_limit

        log.info("Fetching top %d posts from r/%s (time_filter=day)", limit, subreddit)
        sub = self._reddit.subreddit(subreddit)
        posts: list[Post] = []

        for submission in sub.top(time_filter="day", limit=limit):
            comments = self._fetch_comments(submission)
            post = Post(
                id=submission.id,
                title=submission.title,
                selftext=submission.selftext,
                author=str(submission.author) if submission.author else "[deleted]",
                score=submission.score,
                num_comments=submission.num_comments,
                created_at=datetime.fromtimestamp(submission.created_utc, tz=timezone.utc),
                url=submission.url,
                comments=comments,
            )
            posts.append(post)
            log.debug(
                "Post %s | score=%d | comments=%d | %r",
                post.id,
                post.score,
                len(post.comments),
                post.title,
            )

        log.info("Fetched %d posts from r/%s", len(posts), subreddit)
        return posts

    def _fetch_comments(self, submission: praw.models.Submission) -> list[Comment]:
        """Fetch and flatten comments for a submission, returning the top N by score.

        Calls replace_more(limit=0) to flatten the comment tree without
        issuing additional API requests for 'load more' stubs.

        Returns:
            List of Comment objects sorted by score descending.
        """
        limit = self._config.reddit.comment_limit

        submission.comments.replace_more(limit=0)
        all_comments: list[praw.models.Comment] = submission.comments.list()
        top_comments = sorted(all_comments, key=lambda c: c.score, reverse=True)[:limit]

        return [
            Comment(
                id=c.id,
                post_id=submission.id,
                body=c.body,
                author=str(c.author) if c.author else "[deleted]",
                score=c.score,
                created_at=datetime.fromtimestamp(c.created_utc, tz=timezone.utc),
            )
            for c in top_comments
        ]
