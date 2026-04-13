from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_serializer

from .location import TechnicianLocationRead, _normalize_for_display


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
        return _normalize_for_display(value)
