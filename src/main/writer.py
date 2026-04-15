"""Abstract writer interface."""

from __future__ import annotations

from main.models import AnalysisResult, Post


class AbstractWriter:
    """Base writer interface for raw posts and analytical results."""

    def write_raw_posts(self, posts: list[Post]) -> None:
        pass

    def write_analytical_results(self, results: list[AnalysisResult]) -> None:
        pass
