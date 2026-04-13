from __future__ import annotations

from enum import Enum

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class UserRole(str, Enum):
    TECHNICIAN = "technician"
    MANAGER = "manager"
    ADMIN = "admin"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    role: Mapped[UserRole] = mapped_column(nullable=False)
    technician_code: Mapped[str | None] = mapped_column(String(50), unique=True, nullable=True)

    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    assignments = relationship("JobAssignment", back_populates="technician", foreign_keys="JobAssignment.technician_id")
    created_jobs = relationship("Job", back_populates="created_by")
    events = relationship("JobEvent", back_populates="actor")
    updates = relationship("JobUpdate", back_populates="author")
    locations = relationship("TechnicianLocation", back_populates="technician")
    presence = relationship("TechnicianPresence", back_populates="technician", uselist=False)
