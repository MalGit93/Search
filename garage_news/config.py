from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path
from typing import Iterable, List, Optional

import yaml


@dataclass
class SourceConfig:
    """Configuration describing a single news source."""

    name: str
    url: str
    type: str = "rss"
    category: Optional[str] = None
    polling_interval_minutes: int = 360
    tags: List[str] = field(default_factory=list)

    def polling_interval(self) -> timedelta:
        return timedelta(minutes=self.polling_interval_minutes)


@dataclass
class AppConfig:
    """Top-level configuration for the pipeline."""

    sources: List[SourceConfig]
    database_path: Path = Path("garage_news.db")


def _load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Config root must be a mapping, got {type(data)!r}")
    return data


def load_config(path: Path | str) -> AppConfig:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)

    raw = _load_yaml(path)
    sources_data = raw.get("sources") or []
    if not isinstance(sources_data, Iterable):
        raise ValueError("'sources' must be a list")

    sources = [SourceConfig(**source) for source in sources_data]
    db_path = raw.get("database_path")
    database_path = Path(db_path) if db_path else AppConfig.__dataclass_fields__["database_path"].default

    return AppConfig(sources=sources, database_path=database_path)
