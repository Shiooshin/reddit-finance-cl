"""Shared data models used across all modules."""

from __future__ import annotations

from datetime import datetime

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


class AnalysisResult(BaseModel):
    post_id: str
    summary: str
    themes: list[str]
    pain_points: list[str]
    recommendations: list[str]
    analyzed_at: datetime
