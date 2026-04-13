from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from ..models.job_event import JobEventType
from ..models.job import JobPriority, JobStatus
from .datetime_utils import normalize_for_display


class JobCreate(BaseModel):
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
