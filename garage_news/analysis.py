from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Iterable, List

from .storage import Article

WORD_RE = re.compile(r"[A-Za-z]{3,}")
STOP_WORDS = {
    "about",
    "after",
    "again",
    "also",
    "another",
    "because",
    "being",
    "between",
    "could",
    "first",
    "great",
    "however",
    "large",
    "other",
    "over",
    "really",
    "should",
    "their",
    "there",
    "these",
    "thing",
    "those",
    "until",
    "where",
    "while",
    "would",
}


@dataclass
class Trend:
    keyword: str
    frequency: int


@dataclass
class Insight:
    summary: str
    trends: List[Trend]
    policy_suggestions: List[str]


def _tokenize(text: str) -> list[str]:
    return [word.lower() for word in WORD_RE.findall(text)]


def summarize_article(article: Article, sentence_limit: int = 3) -> str:
    text = article.content or article.summary or ""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return " ".join(sentences[:sentence_limit]).strip()


def extract_keywords(articles: Iterable[Article], top_k: int = 10) -> list[Trend]:
    counter: Counter[str] = Counter()
    for article in articles:
        text = " ".join(filter(None, [article.title, article.summary, article.content]))
        for token in _tokenize(text):
            if token not in STOP_WORDS:
                counter[token] += 1
    return [Trend(keyword=word, frequency=count) for word, count in counter.most_common(top_k)]


def group_trends_by_category(articles: Iterable[Article]) -> dict[str, list[Trend]]:
    grouped: defaultdict[str, list[Article]] = defaultdict(list)
    for article in articles:
        grouped[article.category or "general"].append(article)
    return {
        category: extract_keywords(items, top_k=5)
        for category, items in grouped.items()
    }


def generate_policy_suggestions(trends: Iterable[Trend]) -> list[str]:
    suggestions: list[str] = []
    for trend in trends:
        keyword = trend.keyword
        suggestions.append(
            f"Investigate targeted guidance or incentives related to '{keyword}', as it appears in recent coverage ({trend.frequency} mentions)."
        )
    return suggestions


def build_insights(articles: list[Article], max_articles: int = 5) -> Insight:
    selected = articles[:max_articles]
    summaries = [f"- {article.title}: {summarize_article(article)}" for article in selected]
    trends = extract_keywords(selected, top_k=8)
    policy_suggestions = generate_policy_suggestions(trends[:3])
    summary_text = "\n".join(summaries)
    return Insight(summary=summary_text, trends=trends, policy_suggestions=policy_suggestions)
