from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from .datetime_utils import normalize_for_display
from .pagination import PaginatedResponse


class TechnicianLocationCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "latitude": 25.2048,
                "longitude": 55.2708,
                "accuracy_meters": 12.5,
                "recorded_at": "2026-04-20T08:15:00+04:00",
            }
        }
    )

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
        return normalize_for_display(value)


class TechnicianLocationLatestRead(TechnicianLocationRead):
    technician_name: str
    is_stale: bool


class TechnicianLocationLatestListResponse(PaginatedResponse[TechnicianLocationLatestRead]):
    pass


class TechnicianLocationHistoryResponse(PaginatedResponse[TechnicianLocationRead]):
    pass
