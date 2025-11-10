from __future__ import annotations

from datetime import timezone
from pathlib import Path
import sys

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from garage_news.config import AppConfig, SourceConfig
from garage_news.pipeline import NewsPipeline


def test_pipeline_continues_after_fetch_error(monkeypatch, tmp_path):
    config = AppConfig(
        sources=[
            SourceConfig(name="Problem Site", url="https://example.com", type="website"),
            SourceConfig(name="Working Feed", url="https://example.com/rss", type="rss"),
        ],
        database_path=tmp_path / "garage_news.db",
    )
    pipeline = NewsPipeline(config)

    def failing_get(*args, **kwargs):  # noqa: ANN001, D401
        """Simulate a network failure for website fetches."""

        raise requests.RequestException("boom")

    monkeypatch.setattr("garage_news.fetchers.website.requests.get", failing_get)

    def fake_rss_fetch_articles(source, limit):  # noqa: ANN001
        yield {
            "title": "Good News",
            "link": "https://example.com/good",
            "summary": "All clear",
        }

    monkeypatch.setattr("garage_news.fetchers.rss.fetch_articles", fake_rss_fetch_articles)

    pipeline.run(limit_per_source=1, fetch_full_content=False)

    articles = pipeline.storage.recent_articles()
    assert [article.title for article in articles] == ["Good News"]
    assert articles[0].fetched_at.tzinfo is timezone.utc


def test_pipeline_advances_after_rss_timeout(monkeypatch, tmp_path):
    config = AppConfig(
        sources=[
            SourceConfig(name="Timing Out Feed", url="https://example.com/rss", type="rss"),
            SourceConfig(name="Working Site", url="https://example.com", type="website"),
        ],
        database_path=tmp_path / "garage_news.db",
    )
    pipeline = NewsPipeline(config)

    def failing_rss_get(*args, **kwargs):  # noqa: ANN001, D401
        """Simulate a timeout when fetching an RSS feed."""

        raise requests.Timeout("took too long")

    monkeypatch.setattr("garage_news.fetchers.rss.requests.get", failing_rss_get)

    def fake_website_fetch_articles(source, limit):  # noqa: ANN001
        yield {
            "title": "Backup News",
            "link": "https://example.com/backup",
            "summary": "We got this",
        }

    monkeypatch.setattr("garage_news.fetchers.website.fetch_articles", fake_website_fetch_articles)

    pipeline.run(limit_per_source=1, fetch_full_content=False)

    articles = pipeline.storage.recent_articles()
    assert [article.title for article in articles] == ["Backup News"]
    assert articles[0].fetched_at.tzinfo is timezone.utc
