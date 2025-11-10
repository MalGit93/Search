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


def test_pipeline_continues_after_rss_timeout(monkeypatch, tmp_path):
    config = AppConfig(
        sources=[
            SourceConfig(name="Slow Feed", url="https://example.com/slow", type="rss"),
            SourceConfig(name="Working Feed", url="https://example.com/rss", type="rss"),
        ],
        database_path=tmp_path / "garage_news.db",
    )
    pipeline = NewsPipeline(config)

    def fake_get(url, *args, **kwargs):  # noqa: ANN001
        if "slow" in url:
            raise requests.Timeout("timed out")

        class DummyResponse:  # noqa: D401
            """Minimal response object for feedparser."""

            def __init__(self, content: bytes):
                self.content = content

            def raise_for_status(self):  # noqa: D401
                """Responses are always OK in this fake."""

                return None

        feed = (
            "<?xml version='1.0' encoding='UTF-8'?>"
            "<rss version='2.0'><channel>"
            "<title>Working</title>"
            "<item><title>Recovered</title><link>https://example.com/good</link>"
            "<description>All clear</description></item>"
            "</channel></rss>"
        )
        return DummyResponse(feed.encode("utf-8"))

    monkeypatch.setattr("garage_news.fetchers.rss.requests.get", fake_get)

    pipeline.run(limit_per_source=1, fetch_full_content=False)

    articles = pipeline.storage.recent_articles()
    assert [article.title for article in articles] == ["Recovered"]
