from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Iterable, Iterator, List, Tuple
from urllib.parse import urlparse

import feedparser
import requests

from ..config import SourceConfig
from ..datetime_utils import ensure_utc
from .website import discover_feed_links


USER_AGENT = "garage-news-bot/0.1"


class RSSFetcher:
    """Retrieve articles from RSS or Atom feeds."""

    def __init__(self, source: SourceConfig):
        if source.type.lower() != "rss":
            raise ValueError("RSSFetcher requires a source with type 'rss'")
        self.source = source

    def fetch(self, limit: int = 5) -> Iterable[dict]:
        feed_url, entries, warnings = self.validate(limit=limit)
        logger = logging.getLogger(__name__)
        for warning in warnings:
            logger.warning(warning)

        if not feed_url:
            logger.error("No usable feed found for %s", self.source.name)
            return

        for entry in entries:
            yield {
                "title": entry.get("title", "Untitled"),
                "link": entry.get("link"),
                "summary": entry.get("summary"),
                "published": self._parse_published(entry),
            }

    def validate(self, limit: int = 5) -> Tuple[str | None, List[feedparser.FeedParserDict], List[str]]:
        """Try to locate a healthy feed for this source.

        Returns a tuple of ``(working_url, entries, warnings)``. ``working_url`` will
        be ``None`` if no feed could be reached. Warnings contain human-friendly
        strings describing any failures or discovery attempts.
        """

        warnings: List[str] = []
        entries, final_url = self._fetch_entries(self.source.url, limit, warnings)
        if entries:
            return final_url, entries, warnings

        logger = logging.getLogger(__name__)
        logger.debug("Attempting discovery for %s", self.source.url)
        for candidate in self._discover_alternatives():
            alt_entries, alt_url = self._fetch_entries(candidate, limit, warnings)
            if alt_entries:
                warnings.append(f"Recovered feed for {self.source.name} at {alt_url}")
                return alt_url, alt_entries, warnings

        warnings.append(f"No valid feeds discovered for {self.source.name}")
        return None, [], warnings

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

    def _fetch_entries(
        self, url: str, limit: int, warnings: List[str]
    ) -> Tuple[List[feedparser.FeedParserDict] | None, str | None]:
        headers = {"User-Agent": USER_AGENT}
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
        except requests.RequestException as exc:
            warnings.append(f"Failed to fetch {url}: {exc}")
            return None, None

        feed = feedparser.parse(response.content)
        if getattr(feed, "bozo", False):
            warnings.append(f"Feed at {response.url} returned parsing errors: {feed.bozo_exception}")

        entries = list(feed.entries[:limit])
        if not entries:
            warnings.append(f"Feed at {response.url} did not return any entries")
            return None, response.url

        return entries, response.url

    def _discover_alternatives(self) -> list[str]:
        """Attempt to find alternate feed URLs from the source root."""

        site_root = self._site_root(self.source.url)
        alternatives = discover_feed_links(site_root)
        if self.source.url in alternatives:
            alternatives.remove(self.source.url)
        return alternatives

    def _site_root(self, url: str) -> str:
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"


def fetch_articles(source: SourceConfig, limit: int = 5) -> Iterator[dict]:
    fetcher = RSSFetcher(source)
    yield from fetcher.fetch(limit=limit)
