from __future__ import annotations

from enum import Enum

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class JobEventType(str, Enum):
    CHECK_IN = "check_in"
    CHECK_OUT = "check_out"


class JobEvent(Base):
    __tablename__ = "job_events"

    id: Mapped[int] = mapped_column(primary_key=True)

    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    event_type: Mapped[JobEventType] = mapped_column(
        SQLEnum(JobEventType, name="job_event_type"), nullable=False
    )
    occurred_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    job = relationship("Job", back_populates="events")
    actor = relationship("User", back_populates="events")
