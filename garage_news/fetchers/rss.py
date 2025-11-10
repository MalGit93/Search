from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, Iterator

import feedparser

from ..config import SourceConfig
from ..datetime_utils import ensure_utc


class RSSFetcher:
    """Retrieve articles from RSS or Atom feeds."""

    def __init__(self, source: SourceConfig):
        if source.type.lower() != "rss":
            raise ValueError("RSSFetcher requires a source with type 'rss'")
        self.source = source

    def fetch(self, limit: int = 5) -> Iterable[dict]:
        feed = feedparser.parse(self.source.url)
        entries = feed.entries[:limit]
        for entry in entries:
            yield {
                "title": entry.get("title", "Untitled"),
                "link": entry.get("link"),
                "summary": entry.get("summary"),
                "published": self._parse_published(entry),
            }

    def _parse_published(self, entry: feedparser.FeedParserDict) -> datetime | None:
        published_parsed = entry.get("published_parsed") or entry.get("updated_parsed")
        if published_parsed:
            return ensure_utc(datetime(*published_parsed[:6], tzinfo=timezone.utc))
        published = entry.get("published") or entry.get("updated")
        if published:
            try:
                parsed = datetime.fromisoformat(published)
            except ValueError:
                return None
            return ensure_utc(parsed)
        return None


def fetch_articles(source: SourceConfig, limit: int = 5) -> Iterator[dict]:
    fetcher = RSSFetcher(source)
    yield from fetcher.fetch(limit=limit)
