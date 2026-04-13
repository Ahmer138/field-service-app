from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


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


class TechnicianLocationLatestRead(TechnicianLocationRead):
    technician_name: str
    is_stale: bool
