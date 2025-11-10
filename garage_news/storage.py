from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
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
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
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
                    published_at.isoformat() if published_at else None,
                    fetched_at.isoformat(),
                    source.category,
                    tags,
                ),
            )

    def recent_articles(self, limit: int = 50) -> list[Article]:
        return self._fetch_articles(
            where_clauses=[],
            params=[],
            limit=limit,
        )

    def articles_between(
        self,
        *,
        start: datetime | None,
        end: datetime | None,
        limit: int | None = None,
    ) -> list[Article]:
        order_expr = "COALESCE(published_at, fetched_at)"
        clauses: list[str] = []
        params: list[object] = []

        if start is not None:
            clauses.append(f"{order_expr} >= ?")
            params.append(start.isoformat())
        if end is not None:
            clauses.append(f"{order_expr} <= ?")
            params.append(end.isoformat())

        return self._fetch_articles(clauses, params, limit=limit, order_expression=order_expr)

    def _fetch_articles(
        self,
        where_clauses: list[str],
        params: list[object],
        *,
        limit: int | None,
        order_expression: str = "COALESCE(published_at, fetched_at)",
    ) -> list[Article]:
        query = (
            "SELECT source_name, source_url, title, link, summary, content, published_at, fetched_at, category, tags "
            f"FROM articles"
        )
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        query += f" ORDER BY {order_expression} DESC"
        query_params = list(params)
        if limit is not None:
            query += " LIMIT ?"
            query_params.append(int(limit))

        with self._connect() as conn:
            cur = conn.execute(query, query_params)
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
