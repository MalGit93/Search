from __future__ import annotations

from datetime import datetime
import logging
from typing import Iterator
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
import requests

from ..config import SourceConfig
from ..datetime_utils import ensure_utc

USER_AGENT = "garage-news-bot/0.1"


def discover_feed_links(page_url: str, timeout: int = 10) -> list[str]:
    """Discover RSS/Atom feeds advertised by a website.

    Many sites expose their feeds via ``<link rel="alternate" type="application/rss+xml">``
    tags on the landing page. This helper fetches the given ``page_url``, scans those
    tags, and returns a list of fully qualified feed URLs. Duplicates are removed while
    preserving the original order.
    """

    headers = {"User-Agent": USER_AGENT}
    try:
        response = requests.get(page_url, headers=headers, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException as exc:
        logging.getLogger(__name__).warning("Failed to discover feeds from %s: %s", page_url, exc)
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    candidates: list[str] = []
    seen: set[str] = set()

    for link_tag in soup.find_all("link", href=True):
        rels = {rel.lower() for rel in (link_tag.get("rel") or [])}
        if "alternate" not in rels:
            continue
        link_type = (link_tag.get("type") or "").lower()
        if not link_type.startswith("application/rss") and "atom" not in link_type and "xml" not in link_type:
            continue

        href = link_tag.get("href", "").strip()
        normalized = _normalize_link(href, response.url)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        candidates.append(normalized)

    return candidates


def fetch_articles(source: SourceConfig, limit: int = 5, timeout: int = 10) -> Iterator[dict]:
    """Scrape a website landing page for recent article links."""

    headers = {"User-Agent": USER_AGENT}
    try:
        response = requests.get(source.url, headers=headers, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException as exc:
        logging.getLogger(__name__).error("Failed to fetch %s: %s", source.url, exc)
        return
    soup = BeautifulSoup(response.text, "html.parser")
    base_url = response.url
    seen: set[str] = set()

    for article in _extract_articles(soup, base_url):
        if article["link"] in seen:
            continue
        seen.add(article["link"])
        yield article
        if len(seen) >= limit:
            return


def _extract_articles(soup: BeautifulSoup, base_url: str) -> Iterator[dict]:
    yield from _extract_from_article_tags(soup, base_url)
    yield from _extract_from_links(soup, base_url)


def _extract_from_article_tags(soup: BeautifulSoup, base_url: str) -> Iterator[dict]:
    for node in soup.find_all("article"):
        link_tag = node.find("a", href=True)
        if not link_tag:
            continue
        link = _normalize_link(link_tag["href"], base_url)
        if not link:
            continue
        title = link_tag.get_text(" ", strip=True) or link
        summary = _first_paragraph_text(node)
        published = _parse_time(node)
        yield {
            "title": title,
            "link": link,
            "summary": summary,
            "published": published,
        }


def _extract_from_links(soup: BeautifulSoup, base_url: str) -> Iterator[dict]:
    base_netloc = urlparse(base_url).netloc
    for link_tag in soup.find_all("a", href=True):
        text = link_tag.get_text(" ", strip=True)
        if not text or len(text) < 20:
            continue
        link = _normalize_link(link_tag["href"], base_url)
        if not link:
            continue
        netloc = urlparse(link).netloc
        if netloc and netloc != base_netloc:
            continue
        yield {
            "title": text,
            "link": link,
            "summary": None,
            "published": None,
        }


def _normalize_link(href: str, base_url: str) -> str | None:
    href = href.strip()
    if not href:
        return None
    if href.startswith("mailto:") or href.startswith("tel:"):
        return None
    full_url = urljoin(base_url, href)
    parsed = urlparse(full_url)
    if not parsed.scheme.startswith("http"):
        return None
    return full_url


def _first_paragraph_text(node) -> str | None:
    paragraph = node.find("p")
    if not paragraph:
        return None
    text = paragraph.get_text(" ", strip=True)
    return text or None


def _parse_time(node) -> datetime | None:
    time_tag = node.find("time")
    if not time_tag:
        return None
    datetime_value = time_tag.get("datetime")
    if not datetime_value:
        return None
    normalized = datetime_value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    return ensure_utc(parsed)
