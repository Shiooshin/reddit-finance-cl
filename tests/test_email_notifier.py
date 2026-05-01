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


def test_send_digest_calls_ses_with_multipart_body(
    patched_config: MagicMock,
) -> None:
    from main.email_notifier import EmailNotifier

    with patch("main.email_notifier.boto3.client") as boto:
        client = boto.return_value
        notifier = EmailNotifier()
        notifier.send_digest([(_post("p1", "Hello"), _result("p1"))])

        client.send_email.assert_called_once()
        kwargs = client.send_email.call_args.kwargs
        assert kwargs["Source"] == "sender@example.com"
        assert kwargs["Destination"] == {"ToAddresses": ["dest@example.com"]}
        body = kwargs["Message"]["Body"]
        assert "Html" in body and "Text" in body
        assert "Hello" in body["Html"]["Data"]
        assert "Hello" in body["Text"]["Data"]
        subject = kwargs["Message"]["Subject"]["Data"]
        assert subject.startswith("[Reddit Insight] 1 new — r/finance_ukr — ")


def test_render_escapes_html_in_post_title(patched_config: MagicMock) -> None:
    """HTML template autoescapes; plaintext template does not need to."""
    from main.email_notifier import EmailNotifier

    with patch("main.email_notifier.boto3.client") as boto:
        client = boto.return_value
        evil_title = "<script>alert(1)</script>"
        notifier = EmailNotifier()
        notifier.send_digest([(_post("p1", evil_title), _result("p1"))])

        body = client.send_email.call_args.kwargs["Message"]["Body"]
        assert "<script>alert(1)</script>" not in body["Html"]["Data"]
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in body["Html"]["Data"]
        assert "<script>alert(1)</script>" in body["Text"]["Data"]


def test_render_includes_one_table_row_per_pair(
    patched_config: MagicMock,
) -> None:
    from main.email_notifier import EmailNotifier

    pairs = [(_post(f"p{i}", f"Title{i}"), _result(f"p{i}")) for i in range(3)]
    with patch("main.email_notifier.boto3.client") as boto:
        client = boto.return_value
        EmailNotifier().send_digest(pairs)

        html = client.send_email.call_args.kwargs["Message"]["Body"]["Html"]["Data"]
        for i in range(3):
            assert f"https://reddit.com/p{i}" in html
            assert f"Title{i}" in html
        subject = client.send_email.call_args.kwargs["Message"]["Subject"]["Data"]
        assert "3 new" in subject
