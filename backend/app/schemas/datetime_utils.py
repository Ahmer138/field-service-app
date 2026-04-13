from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from ..core.config import settings


def normalize_for_display(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=ZoneInfo("UTC"))
    return value.astimezone(ZoneInfo(settings.DISPLAY_TIMEZONE))
