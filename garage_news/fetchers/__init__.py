"""Fetchers for various news source types."""

from . import rss
from .webpage import fetch_article_body

__all__ = ["rss", "fetch_article_body"]
