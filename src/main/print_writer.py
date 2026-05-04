"""PrintWriter — writes analytical results to stdout."""

from __future__ import annotations

from main.models import AnalysisResult, Post
from main.writer import AbstractWriter


class PrintWriter(AbstractWriter):
    """Writes analytical results to stdout. Does not handle raw post storage."""

    def write_raw_posts(self, posts: list[Post]) -> None:
        for post in posts:
            print(f"\n{'=' * 60}")
            print(f"Post:     {post.id}")
            print(f"Title:    {post.title}")
            print(f"Author:   {post.author}")
            print(f"Created:  {post.created_at.strftime('%Y-%m-%d %H:%M UTC')}")
            print(f"URL:      {post.url}")
            if post.selftext:
                print(f"Body:     {post.selftext}")
            if post.comments:
                print("Comments:")
                for comment in post.comments:
                    print(f"  {comment.author}: {comment.body}")
        print(f"\n{'=' * 60}")

    def write_analytical_results(self, results: list[AnalysisResult]) -> None:
        for result in results:
            print(f"\n{'=' * 60}")
            print(f"Post:      {result.post_id}")
            print(
                f"Sentiment: {result.sentiment}"
                f" (confidence: {result.confidence_score}/100)"
            )
            print(f"Summary:   {result.summary}")
            if result.key_topics:
                print(f"Topics:    {', '.join(result.key_topics)}")
            if result.pain_points:
                print("Pain points:")
                for point in result.pain_points:
                    print(f"  - {point}")
            if result.opportunities:
                print("Opportunities:")
                for opp in result.opportunities:
                    print(
                        f"  [{opp.type}] {opp.description}"
                        f" (risk={opp.risk_level}, horizon={opp.time_horizon})"
                    )
            if result.contrarian_insights:
                print("Contrarian:")
                for insight in result.contrarian_insights:
                    print(f"  - {insight}")
        print(f"\n{'=' * 60}")
