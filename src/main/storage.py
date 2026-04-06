"""DuckDB persistence layer for posts, comments, and analysis results."""

from __future__ import annotations

from main.config import get_config
from main.logger import get_logger
from main.models import AnalysisResult, Post

log = get_logger(__name__)


class Storage:
    """Handles all read/write operations against the DuckDB database."""

    def __init__(self) -> None:
        pass

    def save_post(self, post: Post) -> None:
        """Persist a post and its comments. No-op if post ID already exists."""
        pass

    def post_exists(self, post_id: str) -> bool:
        """Return True if the post has already been stored."""
        pass

    def get_unanalyzed_posts(self) -> list[Post]:
        """Return posts that have been stored but not yet analyzed."""
        pass

    def save_analysis(self, result: AnalysisResult) -> None:
        """Persist an analysis result."""
        pass
