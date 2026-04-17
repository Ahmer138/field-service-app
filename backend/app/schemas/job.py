from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from ..models.job_event import JobEventType
from ..models.job import JobPriority, JobStatus
from .datetime_utils import normalize_for_display
from .pagination import PaginatedResponse


class JobCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "title": "Emergency compressor repair",
                "description": "Customer reports no cooling in building A",
                "technician_instructions": "Bring refrigerant gauges and replacement capacitor",
                "internal_notes": "VIP site access requires manager notification",
                "address_line1": "12 Marina Walk",
                "address_line2": "Building A",
                "city": "Dubai",
                "state": "Dubai",
                "postal_code": "10001",
                "country": "UAE",
                "scheduled_start": "2026-04-20T09:00:00+04:00",
                "scheduled_end": "2026-04-20T11:00:00+04:00",
                "priority": "urgent",
            }
        }
    )

    title: str
    description: str | None = None
    technician_instructions: str | None = None
    internal_notes: str | None = None
    address_line1: str
    address_line2: str | None = None
    city: str
    state: str
    postal_code: str
    country: str = "USA"
    scheduled_start: datetime | None = None
    scheduled_end: datetime | None = None
    priority: JobPriority = JobPriority.MEDIUM


class JobUpdate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "in_progress",
                "priority": "high",
                "scheduled_start": "2026-04-21T10:00:00+04:00",
                "scheduled_end": "2026-04-21T12:00:00+04:00",
                "internal_notes": "Customer approved overtime if needed",
            }
        }
    )

    title: str | None = None
    description: str | None = None
    technician_instructions: str | None = None
    internal_notes: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    country: str | None = None
    scheduled_start: datetime | None = None
    scheduled_end: datetime | None = None
    status: JobStatus | None = None
    priority: JobPriority | None = None


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None
    technician_instructions: str | None
    internal_notes: str | None
    address_line1: str
    address_line2: str | None
    city: str
    state: str
    postal_code: str
    country: str
    scheduled_start: datetime | None
    scheduled_end: datetime | None
    status: JobStatus
    priority: JobPriority
    created_by_id: int
    created_at: datetime
    updated_at: datetime

    @field_serializer("scheduled_start", "scheduled_end", "created_at", "updated_at")
    def serialize_datetime(self, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return normalize_for_display(value)


class JobAssignRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={"example": {"technician_id": 7}})

    technician_id: int


class JobAssignmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: int
    technician_id: int
    assigned_by_id: int
    assigned_at: datetime

    @field_serializer("assigned_at")
    def serialize_datetime(self, value: datetime) -> datetime:
        return normalize_for_display(value)


class JobEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: int
    actor_id: int
    event_type: JobEventType
    occurred_at: datetime

    @field_serializer("occurred_at")
    def serialize_datetime(self, value: datetime) -> datetime:
        return normalize_for_display(value)


class JobUpdateCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"example": {"message": "Technician arrived on site and started diagnostics"}}
    )

    message: str


class JobUpdatePhotoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_update_id: int
    file_key: str
    file_name: str | None
    content_type: str | None
    created_at: datetime

    @field_serializer("created_at")
    def serialize_datetime(self, value: datetime) -> datetime:
        return normalize_for_display(value)


class JobUpdateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: int
    author_id: int
    message: str
    created_at: datetime
    photos: list[JobUpdatePhotoRead] = Field(default_factory=list)

    @field_serializer("created_at")
    def serialize_datetime(self, value: datetime) -> datetime:
        return normalize_for_display(value)


class JobUpdatePhotoDownload(BaseModel):
    file_key: str
    download_url: str
    expires_in_seconds: int


class JobListResponse(PaginatedResponse[JobRead]):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total": 1,
                "offset": 0,
                "limit": 50,
                "items": [
                    {
                        "id": 12,
                        "title": "Emergency compressor repair",
                        "description": "Customer reports no cooling in building A",
                        "technician_instructions": "Bring refrigerant gauges and replacement capacitor",
                        "internal_notes": "VIP site access requires manager notification",
                        "address_line1": "12 Marina Walk",
                        "address_line2": "Building A",
                        "city": "Dubai",
                        "state": "Dubai",
                        "postal_code": "10001",
                        "country": "UAE",
                        "scheduled_start": "2026-04-20T09:00:00+04:00",
                        "scheduled_end": "2026-04-20T11:00:00+04:00",
                        "status": "not_started",
                        "priority": "urgent",
                        "created_by_id": 2,
                        "created_at": "2026-04-17T12:10:00+04:00",
                        "updated_at": "2026-04-17T12:10:00+04:00",
                    }
                ],
            }
        }
    )
