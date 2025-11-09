"""Garage news aggregation and analysis toolkit."""

from .pipeline import NewsPipeline
from .config import load_config, SourceConfig

__all__ = [
    "NewsPipeline",
    "load_config",
    "SourceConfig",
]
