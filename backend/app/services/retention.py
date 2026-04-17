from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import JobUpdatePhoto, TechnicianLocation, TechnicianPresence


def _normalize_to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


@dataclass
class RetentionRunSummary:
    dry_run: bool
    executed_at: datetime
    location_cutoff: datetime
    presence_cutoff: datetime
    photo_cutoff: datetime
    location_rows_deleted: int = 0
    presence_rows_deleted: int = 0
    photo_rows_deleted: int = 0
    photo_delete_failures: int = 0

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        for key in ("executed_at", "location_cutoff", "presence_cutoff", "photo_cutoff"):
            payload[key] = payload[key].isoformat()
        return payload

    @property
    def has_failures(self) -> bool:
        return self.photo_delete_failures > 0


def _collect_location_ids_to_delete(db: Session, *, cutoff: datetime) -> list[int]:
    locations = db.scalars(
        select(TechnicianLocation).order_by(
            TechnicianLocation.technician_id.asc(),
            TechnicianLocation.recorded_at.desc(),
            TechnicianLocation.id.desc(),
        )
    ).all()

    latest_seen: set[int] = set()
    location_ids_to_delete: list[int] = []
    for location in locations:
        if location.technician_id not in latest_seen:
            latest_seen.add(location.technician_id)
            continue
        if _normalize_to_utc(location.recorded_at) < cutoff:
            location_ids_to_delete.append(location.id)
    return location_ids_to_delete


def run_retention(
    db: Session,
    *,
    storage_service,
    now: datetime | None = None,
    dry_run: bool = False,
) -> RetentionRunSummary:
    executed_at = _normalize_to_utc(now or datetime.now(timezone.utc))
    location_cutoff = executed_at - timedelta(days=settings.LOCATION_RETENTION_DAYS)
    presence_cutoff = executed_at - timedelta(days=settings.PRESENCE_RETENTION_DAYS)
    photo_cutoff = executed_at - timedelta(days=settings.PHOTO_RETENTION_DAYS)

    summary = RetentionRunSummary(
        dry_run=dry_run,
        executed_at=executed_at,
        location_cutoff=location_cutoff,
        presence_cutoff=presence_cutoff,
        photo_cutoff=photo_cutoff,
    )

    location_ids_to_delete = _collect_location_ids_to_delete(db, cutoff=location_cutoff)
    stale_presences = db.scalars(
        select(TechnicianPresence).where(TechnicianPresence.last_seen_at < presence_cutoff)
    ).all()
    stale_photos = db.scalars(
        select(JobUpdatePhoto)
        .where(JobUpdatePhoto.created_at < photo_cutoff)
        .order_by(JobUpdatePhoto.created_at.asc(), JobUpdatePhoto.id.asc())
    ).all()

    summary.location_rows_deleted = len(location_ids_to_delete)
    summary.presence_rows_deleted = len(stale_presences)
    summary.photo_rows_deleted = len(stale_photos)

    if dry_run:
        return summary

    if location_ids_to_delete:
        locations_to_delete = db.scalars(
            select(TechnicianLocation).where(TechnicianLocation.id.in_(location_ids_to_delete))
        ).all()
        for location in locations_to_delete:
            db.delete(location)

    for presence in stale_presences:
        db.delete(presence)

    deleted_photos = 0
    for photo in stale_photos:
        try:
            storage_service.delete_object(photo.file_key)
        except Exception:
            summary.photo_delete_failures += 1
            continue

        db.delete(photo)
        deleted_photos += 1

    summary.photo_rows_deleted = deleted_photos
    db.commit()
    return summary
