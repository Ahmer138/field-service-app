from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_serializer

from .datetime_utils import normalize_for_display
from .location import TechnicianLocationRead
from .pagination import PaginatedResponse


class TechnicianPresenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    technician_id: int
    technician_name: str
    is_logged_in: bool
    is_online: bool
    session_started_at: datetime
    last_seen_at: datetime
    latest_location: TechnicianLocationRead | None = None

    @field_serializer("session_started_at", "last_seen_at")
    def serialize_datetime(self, value: datetime) -> datetime:
        return normalize_for_display(value)


class TechnicianPresenceListResponse(PaginatedResponse[TechnicianPresenceRead]):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total": 1,
                "offset": 0,
                "limit": 50,
                "items": [
                    {
                        "technician_id": 7,
                        "technician_name": "Tech One",
                        "is_logged_in": True,
                        "is_online": True,
                        "session_started_at": "2026-04-17T08:00:00+04:00",
                        "last_seen_at": "2026-04-17T13:05:00+04:00",
                        "latest_location": {
                            "id": 101,
                            "technician_id": 7,
                            "latitude": 25.2048,
                            "longitude": 55.2708,
                            "accuracy_meters": 12.5,
                            "recorded_at": "2026-04-17T13:05:00+04:00",
                            "created_at": "2026-04-17T13:05:00+04:00",
                        },
                    }
                ],
            }
        }
    )
