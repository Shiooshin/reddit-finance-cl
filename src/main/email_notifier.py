"""Sends a digest email containing analysis results via AWS SES."""

from __future__ import annotations

from datetime import date
from typing import Final

import boto3
from botocore.exceptions import ClientError
from jinja2 import Environment, PackageLoader, select_autoescape
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from main.config import get_config
from main.logger import get_logger
from main.models import AnalysisResult, Post

log = get_logger(__name__)

_SENTIMENT_COLORS: Final[dict[str, str]] = {
    "bullish": "#d4edda",
    "bearish": "#f8d7da",
    "neutral": "#e2e3e5",
    "mixed": "#fff3cd",
}


class EmailNotifier:
    """Sends a digest email containing analysis results via AWS SES."""

    def __init__(self) -> None:
        cfg = get_config()
        self._recipients = cfg.email.recipients
        self._from = cfg.email.from_address
        self._subject_prefix = cfg.email.subject_prefix
        self._subreddit = cfg.reddit.subreddit
        self._client = boto3.client("ses", region_name=cfg.email.aws_region)
        self._env = Environment(
            loader=PackageLoader("main", "templates"),
            autoescape=select_autoescape(["html"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def send_digest(self, pairs: list[tuple[Post, AnalysisResult]]) -> None:
        if not pairs or not self._recipients:
            log.info(
                "Skipping email: pairs=%d recipients=%d",
                len(pairs),
                len(self._recipients),
            )
            return
        raise NotImplementedError("render+send wired in Task 7")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(ClientError),
        reraise=True,
    )
    def _send(self, subject: str, html: str, text: str) -> None:
        self._client.send_email(
            Source=self._from,
            Destination={"ToAddresses": self._recipients},
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {
                    "Html": {"Data": html, "Charset": "UTF-8"},
                    "Text": {"Data": text, "Charset": "UTF-8"},
                },
            },
        )
