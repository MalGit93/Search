"""Utilities for working with timezone aware datetimes."""
from __future__ import annotations

from datetime import datetime, timezone


def ensure_utc(dt: datetime | None) -> datetime | None:
    """Return a copy of ``dt`` that is normalized to UTC.

    The storage layer expects timestamps to be comparable regardless of their
    origin. Incoming values from feeds or scrapers may be naive (lacking a
    timezone) or use a non-UTC offset. For naive values we assume the timestamp
    is already in UTC and attach :class:`datetime.timezone.utc`. For aware
    values we convert them to UTC.
    """

    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
