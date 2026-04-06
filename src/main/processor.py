"""Text cleaning and chunking for LLM context preparation."""

from __future__ import annotations

from main.logger import get_logger
from main.models import Post

log = get_logger(__name__)


class Processor:
    """Cleans and prepares post text before it is sent to the analyzer."""

    def clean(self, post: Post) -> Post:
        """Strip URLs, markdown, and noise from post title and body."""
        pass

    def chunk(self, text: str, max_chars: int = 8000) -> list[str]:
        """Split long text into chunks that fit within LLM context limits."""
        pass
