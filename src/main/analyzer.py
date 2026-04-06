"""LLM-based financial insight extraction using the OpenAI Chat Completions API."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import openai

from main.config import get_config
from main.logger import get_logger
from main.models import AnalysisResult, Opportunity, Post

log = get_logger(__name__)

_SYSTEM_PROMPT = """\
You are a senior financial analyst, market researcher, and opportunity scout. \
Your job is to extract high-value, actionable financial insights from Reddit discussions.

## Your role
- Identify what users are worried about, excited by, or asking for — even when it is not stated explicitly.
- Detect early trends, emerging demand, and asymmetric opportunities (high potential upside, currently low awareness).
- Prioritise signal over noise. Ignore off-topic, joke, or irrelevant comments entirely.
- Focus on patterns that repeat across multiple comments — these carry more weight than single opinions.
- Extract implicit signals (what users imply or assume) not only explicit statements.

## Output rules
- Return ONLY a valid JSON object. No markdown, no explanation, no extra text.
- If you are unsure about a field, use "unknown" for strings or an empty list for arrays.
- confidence_score reflects how much clear financial signal was present in the discussion (0 = noise only, 100 = very strong signal).

## Required JSON structure
{
  "summary": "2-3 sentence summary of the discussion from a financial lens",
  "sentiment": "bullish | bearish | neutral | mixed",
  "key_topics": ["topic1", "topic2"],
  "pain_points": ["problem or frustration raised by users"],
  "user_intents": ["what users are trying to achieve or find"],
  "market_signals": ["trends, demand patterns, or behavioural signals worth noting"],
  "opportunities": [
    {
      "type": "investment | product | business | content",
      "description": "what the opportunity is",
      "rationale": "why this discussion supports it",
      "risk_level": "low | medium | high",
      "time_horizon": "short | medium | long"
    }
  ],
  "contrarian_insights": ["non-obvious or counter-consensus observations"],
  "confidence_score": 0
}
"""


def _build_user_message(post: Post) -> str:
    """Format a post and its comments as plain text for the LLM."""
    lines = [
        f"Post title: {post.title}",
        f"Post body: {post.selftext or '(no body)'}",
        "",
        "Top comments:",
    ]
    for comment in post.comments:
        lines.append(f"- {comment.body}")
    return "\n".join(lines)


class Analyzer:
    """Extracts structured financial insights from a Reddit post via OpenAI."""

    def __init__(self) -> None:
        cfg = get_config().openai
        self._client = openai.OpenAI(api_key=cfg.api_key)
        self._model = cfg.model
        self._max_tokens = cfg.max_tokens

    def analyze(self, post: Post) -> AnalysisResult:
        """Run financial insight extraction for a single post.

        Makes one Chat Completions call and parses the JSON response
        into a fully validated AnalysisResult.
        """
        log.info("Analyzing post %s: %r", post.id, post.title)

        response = self._client.chat.completions.create(
            model=self._model,
            temperature=0.2,
            max_tokens=self._max_tokens,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": _build_user_message(post)},
            ],
        )

        raw = response.choices[0].message.content or "{}"
        data = json.loads(raw)

        opportunities = [
            Opportunity(
                type=o.get("type", "investment"),
                description=o.get("description", ""),
                rationale=o.get("rationale", ""),
                risk_level=o.get("risk_level", "medium"),
                time_horizon=o.get("time_horizon", "medium"),
            )
            for o in data.get("opportunities", [])
        ]

        result = AnalysisResult(
            post_id=post.id,
            summary=data.get("summary", ""),
            sentiment=data.get("sentiment", "neutral"),
            key_topics=data.get("key_topics", []),
            pain_points=data.get("pain_points", []),
            user_intents=data.get("user_intents", []),
            market_signals=data.get("market_signals", []),
            opportunities=opportunities,
            contrarian_insights=data.get("contrarian_insights", []),
            confidence_score=int(data.get("confidence_score", 0)),
            analyzed_at=datetime.now(tz=timezone.utc),
        )

        log.debug(
            "Post %s | sentiment=%s | topics=%d | opportunities=%d | confidence=%d",
            post.id,
            result.sentiment,
            len(result.key_topics),
            len(result.opportunities),
            result.confidence_score,
        )

        return result
