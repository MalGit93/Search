from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from garage_news.config import SourceConfig
from garage_news.storage import Storage


def make_source(name: str = "Example") -> SourceConfig:
    return SourceConfig(name=name, url="https://example.com/rss", tags=["tag"])


def test_recent_articles_orders_by_normalized_published_at(tmp_path):
    storage = Storage(tmp_path / "articles.db")
    source = make_source()

    storage.upsert_article(
        source=source,
        title="Earlier UTC",
        link="https://example.com/1",
        summary=None,
        content=None,
        published_at=datetime(2024, 3, 1, 12, 0, tzinfo=timezone.utc),
        fetched_at=datetime.now(timezone.utc),
    )

    storage.upsert_article(
        source=source,
        title="Offset Ahead",
        link="https://example.com/2",
        summary=None,
        content=None,
        published_at=datetime(2024, 3, 1, 9, 0, tzinfo=timezone(timedelta(hours=-4))),
        fetched_at=datetime.now(timezone.utc),
    )

    storage.upsert_article(
        source=source,
        title="Naive Latest",
        link="https://example.com/3",
        summary=None,
        content=None,
        published_at=datetime(2024, 3, 1, 13, 30),
        fetched_at=datetime.now(timezone.utc),
    )

    articles = storage.recent_articles(limit=3)

    assert [article.title for article in articles] == [
        "Naive Latest",
        "Offset Ahead",
        "Earlier UTC",
    ]
    assert articles[0].published_at.tzinfo == timezone.utc
    assert articles[1].published_at.tzinfo == timezone.utc
    assert articles[2].published_at.tzinfo == timezone.utc
