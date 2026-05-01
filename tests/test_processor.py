"""Tests for Processor.process() return shape."""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

from main.models import AnalysisResult, Post
from main.processor import Processor


def _make_post(post_id: str, title: str = "Title") -> Post:
    return Post(
        id=post_id,
        title=title,
        selftext="body",
        author="alice",
        score=10,
        num_comments=0,
        created_at=datetime.now(tz=UTC),
        url=f"https://reddit.com/{post_id}",
        comments=[],
    )


def _make_result(post_id: str) -> AnalysisResult:
    return AnalysisResult(
        post_id=post_id,
        summary="s",
        sentiment="neutral",
        key_topics=[],
        pain_points=[],
        user_intents=[],
        market_signals=[],
        opportunities=[],
        contrarian_insights=[],
        confidence_score=50,
        analyzed_at=datetime.now(tz=UTC),
    )


def test_process_returns_pairs_of_original_post_and_result() -> None:
    posts = [_make_post("p1", "First"), _make_post("p2", "Second")]
    analyzer = MagicMock()
    analyzer.analyze.side_effect = [_make_result("p1"), _make_result("p2")]

    pairs = Processor().process(posts, analyzer)

    assert len(pairs) == 2
    assert pairs[0][0].id == "p1"
    assert pairs[0][0].title == "First"
    assert pairs[0][1].post_id == "p1"
    assert pairs[1][0].id == "p2"
    assert pairs[1][1].post_id == "p2"


def test_process_passes_cleaned_post_to_analyzer_not_original() -> None:
    """clean_post strips URLs from title; analyzer receives the cleaned copy,
    but the pair returned to caller keeps the original post."""
    post = _make_post("p1", title="Title with https://example.com link")
    analyzer = MagicMock()
    analyzer.analyze.return_value = _make_result("p1")

    pairs = Processor().process([post], analyzer)

    cleaned_arg = analyzer.analyze.call_args.args[0]
    assert "https://example.com" not in cleaned_arg.title
    assert "https://example.com" in pairs[0][0].title
