from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from garage_news.config import SourceConfig
from garage_news.storage import Storage


class StorageTransactionTests(TestCase):
    def test_transaction_rolls_back_on_error(self) -> None:
        with TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            storage = Storage(db_path)
            source = SourceConfig(name="Example", url="https://example.com", tags=["news"])

            with self.assertRaises(sqlite3.OperationalError):
                with storage._connect() as conn:
                    conn.execute("INSERT INTO missing_table VALUES (1)")

            storage.upsert_article(
                source=source,
                title="Example title",
                link="https://example.com/article",
                summary="Summary",
                content="Content",
                published_at=datetime.now(),
                fetched_at=datetime.now(),
            )

            articles = storage.recent_articles()

            self.assertEqual(1, len(articles))
            self.assertEqual("Example title", articles[0].title)
