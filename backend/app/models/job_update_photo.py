from __future__ import annotations

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class JobUpdatePhoto(Base):
    __tablename__ = "job_update_photos"

    id: Mapped[int] = mapped_column(primary_key=True)

    job_update_id: Mapped[int] = mapped_column(
        ForeignKey("job_updates.id", ondelete="CASCADE"), nullable=False
    )

    file_key: Mapped[str] = mapped_column(String(500), nullable=False)
    file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(100), nullable=True)

    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    job_update = relationship("JobUpdate", back_populates="photos")
