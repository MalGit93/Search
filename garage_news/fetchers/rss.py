from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Iterable, Iterator

import feedparser
import requests

from ..config import SourceConfig
from ..datetime_utils import ensure_utc

USER_AGENT = "garage-news-bot/0.1"


class RSSFetcher:
    """Retrieve articles from RSS or Atom feeds."""

    def __init__(self, source: SourceConfig):
        if source.type.lower() != "rss":
            raise ValueError("RSSFetcher requires a source with type 'rss'")
        self.source = source

    def fetch(self, limit: int = 5, timeout: int = 10) -> Iterable[dict]:
        headers = {"User-Agent": USER_AGENT}
        try:
            response = requests.get(self.source.url, headers=headers, timeout=timeout)
            response.raise_for_status()
        except requests.RequestException as exc:
            logging.getLogger(__name__).error("Failed to fetch %s: %s", self.source.url, exc)
            return

        feed = feedparser.parse(response.content)
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


def fetch_articles(source: SourceConfig, limit: int = 5, timeout: int = 10) -> Iterator[dict]:
    fetcher = RSSFetcher(source)
    yield from fetcher.fetch(limit=limit, timeout=timeout)
