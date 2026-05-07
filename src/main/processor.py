"""Text cleaning and preparation for LLM input."""

from __future__ import annotations

import html
import re

from main.analyzer import Analyzer
from main.config import get_config
from main.logger import get_logger
from main.models import AnalysisResult, Comment, Post

log = get_logger(__name__)

_MAX_TEXT_LENGTH = 1000

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_URL_RE = re.compile(r"https?://\S+|www\.\S+")
_WHITESPACE_RE = re.compile(r"\s+")

_DELETED_MARKERS = {"[deleted]", "[removed]"}


class Processor:
    """Cleans post and comment text to produce LLM-ready input."""

    def process(
        self, posts: list[Post], analyzer: Analyzer
    ) -> list[tuple[Post, AnalysisResult]]:
        """Clean each post, run LLM analysis, return (original_post, result) pairs.

        The original (un-cleaned) post is paired with the result so downstream
        consumers (e.g. EmailNotifier) keep the un-truncated title and original URL.
        """
        pairs: list[tuple[Post, AnalysisResult]] = []
        for post in posts:
            cleaned = self.clean_post(post)
            result = analyzer.analyze(cleaned)
            log.info(
                "Analyzed post %s | sentiment=%s | confidence=%d",
                post.id,
                result.sentiment,
                result.confidence_score,
            )
            pairs.append((post, result))
        return pairs

    def clean_post(self, post: Post) -> Post:
        """Return a copy of the post with cleaned title, body, and comments.

        - Removes deleted/empty comments
        - Strips URLs from all text fields
        - Normalises whitespace
        - Truncates selftext and comment bodies to _MAX_TEXT_LENGTH chars
        """
        comment_limit = get_config().reddit.comment_limit
        cleaned_comments = [
            self._clean_comment(c)
            for c in post.comments
            if not self._is_empty(c.body)
        ][:comment_limit]

        log.debug(
            "Post %s: %d → %d comments after cleaning",
            post.id,
            len(post.comments),
            len(cleaned_comments),
        )

        return post.model_copy(
            update={
                "title": self._clean_text(post.title, truncate=False),
                "selftext": self._clean_text(post.selftext),
                "comments": cleaned_comments,
            }
        )

    def _clean_comment(self, comment: Comment) -> Comment:
        return comment.model_copy(
            update={"body": self._clean_text(comment.body)}
        )

    def _clean_text(self, text: str, truncate: bool = True) -> str:
        """Decode HTML entities, strip tags, strip URLs, normalise whitespace."""
        text = html.unescape(text)
        text = _HTML_TAG_RE.sub(" ", text)
        text = _URL_RE.sub("", text)
        text = _WHITESPACE_RE.sub(" ", text).strip()
        if truncate and len(text) > _MAX_TEXT_LENGTH:
            text = text[:_MAX_TEXT_LENGTH]
        return text

    def _is_empty(self, text: str) -> bool:
        """Return True for deleted, removed, or blank comment bodies."""
        return not text or text.strip() in _DELETED_MARKERS
