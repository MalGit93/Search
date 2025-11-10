from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

from .config import SourceConfig

SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_name TEXT NOT NULL,
    source_url TEXT NOT NULL,
    title TEXT NOT NULL,
    link TEXT NOT NULL UNIQUE,
    summary TEXT,
    content TEXT,
    published_at TEXT,
    fetched_at TEXT NOT NULL,
    category TEXT,
    tags TEXT
);
"""


@dataclass
class Article:
    source_name: str
    source_url: str
    title: str
    link: str
    summary: Optional[str]
    content: Optional[str]
    published_at: Optional[datetime]
    fetched_at: datetime
    category: Optional[str]
    tags: str


def _to_utc_iso(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat()


class Storage:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        try:
            yield conn
        finally:
            conn.commit()
            conn.close()

    def upsert_article(
        self,
        *,
        source: SourceConfig,
        title: str,
        link: str,
        summary: Optional[str],
        content: Optional[str],
        published_at: Optional[datetime],
        fetched_at: datetime,
    ) -> None:
        tags = ",".join(source.tags)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO articles (source_name, source_url, title, link, summary, content, published_at, fetched_at, category, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(link) DO UPDATE SET
                    title=excluded.title,
                    summary=excluded.summary,
                    content=excluded.content,
                    published_at=excluded.published_at,
                    fetched_at=excluded.fetched_at,
                    category=excluded.category,
                    tags=excluded.tags
                """,
                (
                    source.name,
                    source.url,
                    title,
                    link,
                    summary,
                    content,
                    _to_utc_iso(published_at),
                    _to_utc_iso(fetched_at),
                    source.category,
                    tags,
                ),
            )

    def recent_articles(self, limit: int = 50) -> list[Article]:
        with self._connect() as conn:
            cur = conn.execute(
                "SELECT source_name, source_url, title, link, summary, content, published_at, fetched_at, category, tags "
                "FROM articles ORDER BY COALESCE(published_at, fetched_at) DESC LIMIT ?",
                (limit,),
            )
            rows = cur.fetchall()
        return [
            Article(
                source_name=row[0],
                source_url=row[1],
                title=row[2],
                link=row[3],
                summary=row[4],
                content=row[5],
                published_at=datetime.fromisoformat(row[6]) if row[6] else None,
                fetched_at=datetime.fromisoformat(row[7]),
                category=row[8],
                tags=row[9] or "",
            )
            for row in rows
        ]
