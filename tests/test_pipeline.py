"""Tests for Pipeline orchestration, including email-notifier isolation."""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from main.models import AnalysisResult, Post


def _post(post_id: str = "p1") -> Post:
    return Post(
        id=post_id,
        title="t",
        selftext="b",
        author="alice",
        score=1,
        num_comments=0,
        created_at=datetime.now(tz=UTC),
        url=f"https://reddit.com/{post_id}",
        comments=[],
    )


def _result(post_id: str = "p1") -> AnalysisResult:
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
        confidence_score=10,
        analyzed_at=datetime.now(tz=UTC),
    )


@pytest.fixture
def stubbed_pipeline(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[object, dict[str, MagicMock]]:
    """Stub every collaborator before Pipeline.__init__ instantiates them."""
    stubs = {
        "scraper": MagicMock(),
        "processor": MagicMock(),
        "analyzer": MagicMock(),
        "writer": MagicMock(),
        "notifier": MagicMock(),
    }
    monkeypatch.setattr("main.pipeline.get_scraper", lambda _name: stubs["scraper"])
    monkeypatch.setattr("main.pipeline.Processor", lambda: stubs["processor"])
    monkeypatch.setattr("main.pipeline.Analyzer", lambda: stubs["analyzer"])
    monkeypatch.setattr("main.pipeline.DuckDBWriter", lambda: stubs["writer"])
    monkeypatch.setattr("main.pipeline.EmailNotifier", lambda: stubs["notifier"])

    from main.pipeline import Pipeline
    return Pipeline(), stubs


def test_pipeline_calls_notifier_after_writer(
    stubbed_pipeline: tuple[object, dict[str, MagicMock]],
) -> None:
    pipeline, stubs = stubbed_pipeline
    pairs = [(_post("p1"), _result("p1"))]
    stubs["scraper"].fetch_posts.return_value = [_post("p1")]
    stubs["writer"].post_exists.return_value = False
    stubs["processor"].process.return_value = pairs

    pipeline.run()

    stubs["writer"].write_analytical_results.assert_called_once_with([pairs[0][1]])
    stubs["notifier"].send_digest.assert_called_once_with(pairs)


def test_pipeline_swallows_notifier_failure(
    stubbed_pipeline: tuple[object, dict[str, MagicMock]],
) -> None:
    pipeline, stubs = stubbed_pipeline
    pairs = [(_post("p1"), _result("p1"))]
    stubs["scraper"].fetch_posts.return_value = [_post("p1")]
    stubs["writer"].post_exists.return_value = False
    stubs["processor"].process.return_value = pairs
    stubs["notifier"].send_digest.side_effect = RuntimeError("boom")

    pipeline.run()

    stubs["writer"].write_analytical_results.assert_called_once()


def test_pipeline_skips_notifier_when_no_new_posts(
    stubbed_pipeline: tuple[object, dict[str, MagicMock]],
) -> None:
    pipeline, stubs = stubbed_pipeline
    stubs["scraper"].fetch_posts.return_value = [_post("p1")]
    stubs["writer"].post_exists.return_value = True

    pipeline.run()

    stubs["processor"].process.assert_not_called()
    stubs["writer"].write_analytical_results.assert_not_called()
    stubs["notifier"].send_digest.assert_not_called()
