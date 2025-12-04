from __future__ import annotations

from garage_news import scraper
from garage_news.simple_html import BeautifulSoup


def test_extract_headline_prefers_meta_title():
    soup = BeautifulSoup(
        """
        <html>
          <head>
            <meta property="og:title" content="OG Headline" />
            <title>Fallback Title</title>
          </head>
          <body><h1>Page H1</h1></body>
        </html>
        """
    )

    assert scraper.extract_headline(soup) == "OG Headline"


def test_extract_article_text_filters_short_paragraphs():
    soup = BeautifulSoup(
        """
        <article>
            <p>Short blurb</p>
            <p>Long body text Long body text Long body text Long body text Long body text</p>
            <p>Another sentence that is long enough to keep.</p>
        </article>
        """
    )

    text = scraper.extract_article_text(soup, min_paragraph_length=30)

    assert "Short blurb" not in text
    assert "Long body text" in text
    assert "Another sentence" in text


def test_find_article_links_limits_to_domain_and_keywords(monkeypatch):
    html = """
    <html><body>
      <a href="/news/story-1">Story 1</a>
      <a href="/about">About</a>
      <a href="https://other.com/news/story-2">Offsite</a>
      <a href="#skip">Skip</a>
      <a href="/article/2024/feature">Feature</a>
    </body></html>
    """

    def fake_get_soup(url: str, *, timeout: int = 15):
        return BeautifulSoup(html)

    monkeypatch.setattr(scraper, "get_soup", fake_get_soup)

    links = scraper.find_article_links("https://example.com/listing")

    assert links == [
        "https://example.com/article/2024/feature",
        "https://example.com/news/story-1",
    ]


def test_collect_all_articles_builds_records(monkeypatch):
    listing_html = """
    <html><body>
      <a href="/news/story-1">Story 1</a>
      <a href="/news/story-2">Story 2</a>
    </body></html>
    """

    article_template = """
    <html><head><title>{title}</title></head>
      <body><article><p>{body}</p></article></body>
    </html>
    """

    def fake_get_soup(url: str, *, timeout: int = 15):
        if "listing" in url:
            return BeautifulSoup(listing_html)
        suffix = url[-1]
        return BeautifulSoup(
            article_template.format(title=f"Headline {suffix}", body="Content " * 20),
        )

    monkeypatch.setattr(scraper, "get_soup", fake_get_soup)

    records = scraper.collect_all_articles(["https://example.com/listing"], timeout=5, min_paragraph_length=20)

    assert len(records) == 2
    assert {record.article_url for record in records} == {
        "https://example.com/news/story-1",
        "https://example.com/news/story-2",
    }
    assert all(record.website == "example.com" for record in records)
    assert all(record.headline.startswith("Headline") for record in records)
    assert all(len(record.content) > 0 for record in records)
