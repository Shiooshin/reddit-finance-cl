"""Shared data models used across all modules."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class Comment(BaseModel):
    id: str
    post_id: str
    body: str
    author: str
    score: int
    created_at: datetime


class Post(BaseModel):
    id: str
    title: str
    selftext: str
    author: str
    score: int
    num_comments: int
    created_at: datetime
    url: str
    comments: list[Comment] = []


class Opportunity(BaseModel):
    type: Literal["investment", "product", "business", "content"]
    description: str
    rationale: str
    risk_level: Literal["low", "medium", "high"]
    time_horizon: Literal["short", "medium", "long"]


class AnalysisResult(BaseModel):
    post_id: str
    summary: str
    sentiment: Literal["bullish", "bearish", "neutral", "mixed"]
    key_topics: list[str]
    pain_points: list[str]
    user_intents: list[str]
    market_signals: list[str]
    opportunities: list[Opportunity]
    contrarian_insights: list[str]
    confidence_score: int
    analyzed_at: datetime
