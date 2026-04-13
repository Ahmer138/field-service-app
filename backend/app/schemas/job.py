from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.job_event import JobEventType
from app.models.job import JobPriority, JobStatus


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


class JobAssignRequest(BaseModel):
    technician_id: int


class JobAssignmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: int
    technician_id: int
    assigned_by_id: int
    assigned_at: datetime


class JobEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: int
    actor_id: int
    event_type: JobEventType
    occurred_at: datetime


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


class JobUpdateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: int
    author_id: int
    message: str
    created_at: datetime
    photos: list[JobUpdatePhotoRead] = Field(default_factory=list)
