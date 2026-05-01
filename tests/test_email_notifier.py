"""Tests for EmailNotifier."""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from main.models import AnalysisResult, Post


def _post(post_id: str = "p1", title: str = "Hello") -> Post:
    return Post(
        id=post_id,
        title=title,
        selftext="body",
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
        summary="A summary.",
        sentiment="bullish",
        key_topics=["t1"],
        pain_points=["pp1"],
        user_intents=[],
        market_signals=[],
        opportunities=[],
        contrarian_insights=[],
        confidence_score=80,
        analyzed_at=datetime.now(tz=UTC),
    )


@pytest.fixture
def patched_config(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Stub get_config() to return a config with one recipient."""
    cfg = MagicMock()
    cfg.email.recipients = ["dest@example.com"]
    cfg.email.from_address = "sender@example.com"
    cfg.email.aws_region = "eu-west-1"
    cfg.email.subject_prefix = "[Reddit Insight]"
    cfg.reddit.subreddit = "finance_ukr"
    monkeypatch.setattr("main.email_notifier.get_config", lambda: cfg)
    return cfg


def test_send_digest_skips_when_no_pairs(patched_config: MagicMock) -> None:
    from main.email_notifier import EmailNotifier

    with patch("main.email_notifier.boto3.client") as boto:
        client = boto.return_value
        notifier = EmailNotifier()
        notifier.send_digest([])
        client.send_email.assert_not_called()


def test_send_digest_skips_when_no_recipients(
    patched_config: MagicMock,
) -> None:
    from main.email_notifier import EmailNotifier

    patched_config.email.recipients = []
    with patch("main.email_notifier.boto3.client") as boto:
        client = boto.return_value
        notifier = EmailNotifier()
        notifier.send_digest([(_post(), _result())])
        client.send_email.assert_not_called()
