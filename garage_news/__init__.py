"""Simple toolkit for scraping news articles from listing pages."""

from .scraper import (
    ArticleRecord,
    collect_all_articles,
    export_csv,
    read_source_file,
)

__all__ = [
    "ArticleRecord",
    "collect_all_articles",
    "export_csv",
    "read_source_file",
]
