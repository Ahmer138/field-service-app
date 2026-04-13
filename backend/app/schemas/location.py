from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from ..core.config import settings


def _normalize_for_display(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=ZoneInfo("UTC"))
    return value.astimezone(ZoneInfo(settings.DISPLAY_TIMEZONE))


class TechnicianLocationCreate(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    accuracy_meters: float | None = Field(default=None, ge=0)
    recorded_at: datetime | None = None


class TechnicianLocationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    technician_id: int
    latitude: float
    longitude: float
    accuracy_meters: float | None
    recorded_at: datetime
    created_at: datetime

    @field_serializer("recorded_at", "created_at")
    def serialize_datetime(self, value: datetime) -> datetime:
        return _normalize_for_display(value)


class TechnicianLocationLatestRead(TechnicianLocationRead):
    technician_name: str
    is_stale: bool
