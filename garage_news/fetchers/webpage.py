from __future__ import annotations

from bs4 import BeautifulSoup
import requests


USER_AGENT = "garage-news-bot/0.1"


def fetch_article_body(url: str, timeout: int = 10) -> str | None:
    headers = {"User-Agent": USER_AGENT}
    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    article = soup.find("article")
    if article:
        candidates = article.find_all(["p", "li"])
    else:
        candidates = soup.find_all("p")
    paragraphs = [
        " ".join(node.get_text(strip=True).split())
        for node in candidates
        if node.get_text(strip=True)
    ]
    return "\n\n".join(paragraphs) if paragraphs else None
