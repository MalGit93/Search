"""Fetchers for various news source types."""

from . import rss
from .webpage import fetch_article_body
from . import website

__all__ = ["rss", "website", "fetch_article_body"]
