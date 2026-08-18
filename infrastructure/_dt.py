from __future__ import annotations

from datetime import datetime

FMT = "%Y-%m-%d %H:%M:%S"


def fmt(dt: datetime) -> str:
    return dt.strftime(FMT)


def parse(s: str) -> datetime:
    return datetime.strptime(s, FMT)
