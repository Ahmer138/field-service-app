from __future__ import annotations

from enum import Enum

from sqlalchemy import DateTime, Enum as SQLEnum, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class JobStatus(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class JobPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    technician_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    internal_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    address_line1: Mapped[str] = mapped_column(String(255), nullable=False)
    address_line2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(100), nullable=False)
    postal_code: Mapped[str] = mapped_column(String(20), nullable=False)
    country: Mapped[str] = mapped_column(String(100), nullable=False, default="USA")

    scheduled_start: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scheduled_end: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    status: Mapped[JobStatus] = mapped_column(
        SQLEnum(JobStatus, name="job_status"), nullable=False, default=JobStatus.NOT_STARTED
    )
    priority: Mapped[JobPriority] = mapped_column(
        SQLEnum(JobPriority, name="job_priority"), nullable=False, default=JobPriority.MEDIUM
    )

    created_by_id: Mapped[int] = mapped_column(nullable=False)

    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    created_by = relationship("User", back_populates="created_jobs", foreign_keys=[created_by_id])
    assignments = relationship("JobAssignment", back_populates="job")
    events = relationship("JobEvent", back_populates="job")
    updates = relationship("JobUpdate", back_populates="job")
