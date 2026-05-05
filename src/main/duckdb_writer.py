"""DuckDB persistence layer for posts, comments, and analysis results."""

from __future__ import annotations

import json
from pathlib import Path

import duckdb

from main.config import get_config
from main.logger import get_logger
from main.models import AnalysisResult, Post
from main.writer import AbstractWriter

log = get_logger(__name__)

# TODO(one-time-migration 2026-05-04): schema dropped `score` and
# `num_comments` from posts/comments tables. Pre-existing databases
# from before this date have the old columns and will fail on insert.
# Delete data/insights.duckdb before first run after this commit.
# Once all environments have run on the new schema, this comment
# can be removed.

_CREATE_POSTS = """
CREATE TABLE IF NOT EXISTS posts (
    id         VARCHAR PRIMARY KEY,
    title      VARCHAR NOT NULL,
    selftext   VARCHAR NOT NULL,
    author     VARCHAR NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    url        VARCHAR NOT NULL
)
"""

_CREATE_COMMENTS = """
CREATE TABLE IF NOT EXISTS comments (
    id         VARCHAR PRIMARY KEY,
    post_id    VARCHAR NOT NULL,
    body       VARCHAR NOT NULL,
    author     VARCHAR NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
)
"""

_CREATE_ANALYSIS = """
CREATE TABLE IF NOT EXISTS analysis_results (
    post_id             VARCHAR PRIMARY KEY,
    summary             VARCHAR NOT NULL,
    sentiment           VARCHAR NOT NULL,
    key_topics          JSON NOT NULL,
    pain_points         JSON NOT NULL,
    user_intents        JSON NOT NULL,
    market_signals      JSON NOT NULL,
    opportunities       JSON NOT NULL,
    contrarian_insights JSON NOT NULL,
    confidence_score    INTEGER NOT NULL,
    analyzed_at         TIMESTAMPTZ NOT NULL
)
"""


class DuckDBWriter(AbstractWriter):
    """Persists posts, comments, and analysis results to a DuckDB database."""

    def __init__(self) -> None:
        db_path = get_config().storage.db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = duckdb.connect(db_path)
        self._conn.execute(_CREATE_POSTS)
        self._conn.execute(_CREATE_COMMENTS)
        self._conn.execute(_CREATE_ANALYSIS)
        log.info("DuckDBWriter connected: %s", db_path)

    def write_raw_posts(self, posts: list[Post]) -> None:
        """Persist a list of posts and their comments. Skips already-stored posts."""
        for post in posts:
            self._save_post(post)

    def write_analytical_results(self, results: list[AnalysisResult]) -> None:
        """Persist a list of analysis results."""
        for result in results:
            self._save_analysis(result)

    def post_exists(self, post_id: str) -> bool:
        """Return True if the post has already been stored."""
        row = self._conn.execute(
            "SELECT COUNT(*) FROM posts WHERE id = ?", [post_id]
        ).fetchone()
        return bool(row and row[0] > 0)

    def _save_post(self, post: Post) -> None:
        if self.post_exists(post.id):
            log.debug("Post %s already stored, skipping", post.id)
            return

        self._conn.execute(
            """
            INSERT INTO posts
                (id, title, selftext, author, created_at, url)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [post.id, post.title, post.selftext, post.author,
             post.created_at, post.url],
        )
        for comment in post.comments:
            self._conn.execute(
                """
                INSERT INTO comments (id, post_id, body, author, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                [comment.id, comment.post_id, comment.body,
                 comment.author, comment.created_at],
            )
        log.debug("Saved post %s with %d comments", post.id, len(post.comments))

    def _save_analysis(self, result: AnalysisResult) -> None:
        self._conn.execute(
            """
            INSERT INTO analysis_results (
                post_id, summary, sentiment, key_topics, pain_points,
                user_intents, market_signals, opportunities,
                contrarian_insights, confidence_score, analyzed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                result.post_id,
                result.summary,
                result.sentiment,
                json.dumps(result.key_topics),
                json.dumps(result.pain_points),
                json.dumps(result.user_intents),
                json.dumps(result.market_signals),
                json.dumps([o.model_dump() for o in result.opportunities]),
                json.dumps(result.contrarian_insights),
                result.confidence_score,
                result.analyzed_at,
            ],
        )
        log.debug("Saved analysis for post %s", result.post_id)
