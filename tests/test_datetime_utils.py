from __future__ import annotations

from datetime import datetime, timedelta, timezone

from garage_news.datetime_utils import ensure_utc


def test_ensure_utc_attaches_timezone_to_naive_datetime() -> None:
    naive = datetime(2024, 1, 1, 12, 30, 15)

    result = ensure_utc(naive)

    assert result.tzinfo is timezone.utc
    assert result.isoformat().endswith("+00:00")


def test_ensure_utc_converts_offset_datetime_to_utc() -> None:
    offset = timezone(timedelta(hours=-5))
    aware = datetime(2024, 1, 1, 7, 0, 0, tzinfo=offset)

    result = ensure_utc(aware)

    assert result.tzinfo is timezone.utc
    assert result.hour == 12
    assert result.utcoffset() == timedelta(0)


def test_ensure_utc_preserves_none() -> None:
    assert ensure_utc(None) is None
