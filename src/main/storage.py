"""DuckDB persistence layer for posts, comments, and analysis results."""

from __future__ import annotations

import json
from pathlib import Path

import duckdb

from main.config import get_config
from main.logger import get_logger
from main.models import AnalysisResult, Comment, Post

log = get_logger(__name__)

_CREATE_POSTS = """
CREATE TABLE IF NOT EXISTS posts (
    id           VARCHAR PRIMARY KEY,
    title        VARCHAR NOT NULL,
    selftext     VARCHAR NOT NULL,
    author       VARCHAR NOT NULL,
    score        INTEGER NOT NULL,
    num_comments INTEGER NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL,
    url          VARCHAR NOT NULL
)
"""

_CREATE_COMMENTS = """
CREATE TABLE IF NOT EXISTS comments (
    id         VARCHAR PRIMARY KEY,
    post_id    VARCHAR NOT NULL,
    body       VARCHAR NOT NULL,
    author     VARCHAR NOT NULL,
    score      INTEGER NOT NULL,
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


class Storage:
    """Handles all read/write operations against the DuckDB database."""

    def __init__(self) -> None:
        db_path = get_config().storage.db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = duckdb.connect(db_path)
        self._conn.execute(_CREATE_POSTS)
        self._conn.execute(_CREATE_COMMENTS)
        self._conn.execute(_CREATE_ANALYSIS)
        log.info("Storage connected: %s", db_path)

    def save_post(self, post: Post) -> None:
        """Persist a post and its comments. No-op if post ID already exists."""
        if self.post_exists(post.id):
            log.debug("Post %s already stored, skipping", post.id)
            return

        self._conn.execute(
            """
            INSERT INTO posts
                (id, title, selftext, author, score, num_comments, created_at, url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [post.id, post.title, post.selftext, post.author,
             post.score, post.num_comments, post.created_at, post.url],
        )
        for comment in post.comments:
            self._conn.execute(
                """
                INSERT INTO comments (id, post_id, body, author, score, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [comment.id, comment.post_id, comment.body,
                 comment.author, comment.score, comment.created_at],
            )
        log.debug("Saved post %s with %d comments", post.id, len(post.comments))

    def post_exists(self, post_id: str) -> bool:
        """Return True if the post has already been stored."""
        row = self._conn.execute(
            "SELECT COUNT(*) FROM posts WHERE id = ?", [post_id]
        ).fetchone()
        return bool(row and row[0] > 0)

    def get_unanalyzed_posts(self) -> list[Post]:
        """Return posts that have been stored but not yet analyzed."""
        rows = self._conn.execute(
            """
            SELECT p.id, p.title, p.selftext, p.author, p.score,
                   p.num_comments, p.created_at, p.url
            FROM posts p
            LEFT JOIN analysis_results a ON p.id = a.post_id
            WHERE a.post_id IS NULL
            """
        ).fetchall()

        posts = []
        for row in rows:
            post_id = row[0]
            comments = self._fetch_comments(post_id)
            posts.append(Post(
                id=post_id,
                title=row[1],
                selftext=row[2],
                author=row[3],
                score=row[4],
                num_comments=row[5],
                created_at=row[6],
                url=row[7],
                comments=comments,
            ))
        log.debug("Found %d unanalyzed posts", len(posts))
        return posts

    def _fetch_comments(self, post_id: str) -> list[Comment]:
        rows = self._conn.execute(
            """
            SELECT id, post_id, body, author, score, created_at
            FROM comments WHERE post_id = ?
            """,
            [post_id],
        ).fetchall()
        return [
            Comment(
                id=r[0], post_id=r[1], body=r[2],
                author=r[3], score=r[4], created_at=r[5],
            )
            for r in rows
        ]

    def save_analysis(self, result: AnalysisResult) -> None:
        """Persist an analysis result."""
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
