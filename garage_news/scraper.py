"""Simple news scraper built around listing pages and article extraction."""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Set
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from .simple_html import BeautifulSoup

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; GarageNewsScraper/1.0; +https://example.com/bot)",
}


@dataclass
class ArticleRecord:
    """Structured representation of a scraped article."""

    website: str
    article_url: str
    headline: str
    content: str
    scraped_at: str


def read_source_file(path: Path) -> list[str]:
    """Read listing URLs from a plain text file, ignoring blank lines and comments."""

    lines = []
    if not path.exists():
        return lines

    for raw in path.read_text(encoding="utf-8").splitlines():
        cleaned = raw.strip()
        if not cleaned or cleaned.startswith("#"):
            continue
        lines.append(cleaned)
    return lines


def get_soup(url: str, *, timeout: int = 15) -> Optional[BeautifulSoup]:
    """Fetch a URL and return a parsed HTML document or ``None`` on failure."""

    request = Request(url, headers=DEFAULT_HEADERS)
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310
            charset = response.headers.get_content_charset() or "utf-8"
            html = response.read().decode(charset, errors="replace")
    except Exception:
        return None
    return BeautifulSoup(html)


def _looks_like_article_path(path: str, keywords: Sequence[str]) -> bool:
    """Heuristic to decide if a path resembles a news article."""

    lower_path = path.lower()
    if lower_path in {"", "/", "/news", "/news/"}:
        return False

    if lower_path.count("/") < 2:
        return False

    return any(keyword in lower_path for keyword in keywords)


def find_article_links(
    listing_url: str,
    *,
    timeout: int = 15,
    keywords: Sequence[str] | None = None,
) -> List[str]:
    """Discover likely article links on a news listing page.

    The function keeps links on the same domain as ``listing_url`` and applies
    a handful of heuristics (keyword matching and minimum path depth) to filter
    out obvious navigation links.
    """

    soup = get_soup(listing_url, timeout=timeout)
    if soup is None:
        return []

    base_domain = urlparse(listing_url).netloc
    article_links: Set[str] = set()
    kw_list = list(keywords) if keywords is not None else ["news", "article", "story", "2025", "2024", "2023"]

    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue

        full_url = urljoin(listing_url, href)
        parsed = urlparse(full_url)

        if parsed.netloc != base_domain:
            continue

        if not _looks_like_article_path(parsed.path, kw_list):
            continue

        article_links.add(full_url)

    return sorted(article_links)


def extract_headline(soup: BeautifulSoup) -> str:
    """Extract an article headline using a few common HTML patterns."""

    og = soup.find("meta", property="og:title")
    if og and og.get("content"):
        return og["content"].strip()

    if soup.title and soup.title.string:
        return soup.title.string.strip()

    heading = soup.find("h1")
    if heading:
        return heading.get_text(strip=True)

    return ""


def extract_article_text(soup: BeautifulSoup, *, min_paragraph_length: int = 40) -> str:
    """Extract readable article text from common container patterns."""

    candidates: list[BeautifulSoup] = []

    article_tag = soup.find("article")
    if article_tag:
        candidates.append(article_tag)

    if not candidates:
        for pattern in ["article", "post", "entry", "content", "story"]:
            found = soup.find("div", class_=re.compile(pattern, re.IGNORECASE))
            if found:
                candidates.append(found)
                break

    if not candidates and soup.body:
        candidates.append(soup.body)

    paragraphs: list[str] = []
    for candidate in candidates:
        for paragraph in candidate.find_all("p"):
            text = paragraph.get_text(" ", strip=True)
            if len(text) >= min_paragraph_length:
                paragraphs.append(text)

    return "\n\n".join(paragraphs).strip()


def scrape_article(
    url: str,
    *,
    timeout: int = 15,
    min_paragraph_length: int = 40,
) -> ArticleRecord:
    """Download and parse a single article page into an :class:`ArticleRecord`."""

    soup = get_soup(url, timeout=timeout)
    domain = urlparse(url).netloc
    if soup is None:
        return ArticleRecord(
            website=domain,
            article_url=url,
            headline="",
            content="",
            scraped_at=datetime.now(timezone.utc).isoformat(),
        )

    headline = extract_headline(soup)
    content = extract_article_text(soup, min_paragraph_length=min_paragraph_length)

    return ArticleRecord(
        website=domain,
        article_url=url,
        headline=headline,
        content=content,
        scraped_at=datetime.now(timezone.utc).isoformat(),
    )


def collect_all_articles(
    listing_urls: Iterable[str],
    *,
    timeout: int = 15,
    min_paragraph_length: int = 40,
) -> list[ArticleRecord]:
    """Scrape all articles discovered across listing pages."""

    seen_urls: Set[str] = set()
    records: list[ArticleRecord] = []

    for listing_url in listing_urls:
        article_urls = find_article_links(listing_url, timeout=timeout)
        seen_urls.update(article_urls)

    for article_url in sorted(seen_urls):
        records.append(
            scrape_article(article_url, timeout=timeout, min_paragraph_length=min_paragraph_length)
        )

    return records


def export_csv(records: Iterable[ArticleRecord], destination: Path) -> int:
    """Write article data to a CSV file and return the row count."""

    destination.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["website", "article_url", "headline", "content", "scraped_at"]
    count = 0

    with destination.open("w", newline="", encoding="utf-8-sig") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            writer.writerow(
                {
                    "website": record.website,
                    "article_url": record.article_url,
                    "headline": record.headline,
                    "content": record.content,
                    "scraped_at": record.scraped_at,
                }
            )
            count += 1

    return count
