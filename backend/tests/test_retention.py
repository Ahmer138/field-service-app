from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.models import Job, JobUpdate, JobUpdatePhoto, TechnicianLocation, TechnicianPresence, User
from app.models.job import JobPriority
from app.models.user import UserRole
from app.services.retention import run_retention


class StubStorageService:
    def __init__(self) -> None:
        self.deleted_keys: list[str] = []
        self.failed_keys: set[str] = set()

    def delete_object(self, object_key: str) -> None:
        if object_key in self.failed_keys:
            raise RuntimeError("delete failed")
        self.deleted_keys.append(object_key)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def test_retention_deletes_old_location_history_but_keeps_latest_per_technician(session_factory, monkeypatch):
    now = datetime(2026, 4, 17, 12, 0, tzinfo=timezone.utc)
    monkeypatch.setattr("app.services.retention.settings.LOCATION_RETENTION_DAYS", 30)
    monkeypatch.setattr("app.services.retention.settings.PRESENCE_RETENTION_DAYS", 30)
    monkeypatch.setattr("app.services.retention.settings.PHOTO_RETENTION_DAYS", 180)

    with session_factory() as db:
        technician = User(
            email="retention-tech@example.com",
            password_hash="hashed",
            role=UserRole.TECHNICIAN,
            technician_code="RET-001",
            full_name="Retention Tech",
            is_active=True,
        )
        db.add(technician)
        db.commit()
        db.refresh(technician)

        db.add_all(
            [
                TechnicianLocation(
                    technician_id=technician.id,
                    latitude=25.2,
                    longitude=55.2,
                    accuracy_meters=10,
                    recorded_at=now - timedelta(days=120),
                    created_at=now - timedelta(days=120),
                ),
                TechnicianLocation(
                    technician_id=technician.id,
                    latitude=25.21,
                    longitude=55.21,
                    accuracy_meters=9,
                    recorded_at=now - timedelta(days=60),
                    created_at=now - timedelta(days=60),
                ),
            ]
        )
        db.commit()

        summary = run_retention(db, storage_service=StubStorageService(), now=now)

        remaining_locations = db.query(TechnicianLocation).all()
        assert summary.location_rows_deleted == 1
        assert len(remaining_locations) == 1
        assert _as_utc(remaining_locations[0].recorded_at) == now - timedelta(days=60)


def test_retention_deletes_old_presence_rows(session_factory, monkeypatch):
    now = datetime(2026, 4, 17, 12, 0, tzinfo=timezone.utc)
    monkeypatch.setattr("app.services.retention.settings.LOCATION_RETENTION_DAYS", 30)
    monkeypatch.setattr("app.services.retention.settings.PRESENCE_RETENTION_DAYS", 30)
    monkeypatch.setattr("app.services.retention.settings.PHOTO_RETENTION_DAYS", 180)

    with session_factory() as db:
        technician = User(
            email="presence-retention@example.com",
            password_hash="hashed",
            role=UserRole.TECHNICIAN,
            technician_code="RET-002",
            full_name="Presence Retention",
            is_active=True,
        )
        db.add(technician)
        db.commit()
        db.refresh(technician)

        db.add(
            TechnicianPresence(
                technician_id=technician.id,
                is_logged_in=False,
                session_started_at=now - timedelta(days=45),
                last_seen_at=now - timedelta(days=45),
                updated_at=now - timedelta(days=45),
            )
        )
        db.commit()

        summary = run_retention(db, storage_service=StubStorageService(), now=now)

        assert summary.presence_rows_deleted == 1
        assert db.query(TechnicianPresence).count() == 0


def test_retention_deletes_old_photos_and_skips_rows_when_object_delete_fails(session_factory, monkeypatch):
    now = datetime(2026, 4, 17, 12, 0, tzinfo=timezone.utc)
    monkeypatch.setattr("app.services.retention.settings.LOCATION_RETENTION_DAYS", 30)
    monkeypatch.setattr("app.services.retention.settings.PRESENCE_RETENTION_DAYS", 30)
    monkeypatch.setattr("app.services.retention.settings.PHOTO_RETENTION_DAYS", 180)

    with session_factory() as db:
        manager = User(
            email="photo-retention-manager@example.com",
            password_hash="hashed",
            role=UserRole.MANAGER,
            full_name="Photo Retention Manager",
            is_active=True,
        )
        db.add(manager)
        db.commit()
        db.refresh(manager)

        job = Job(
            title="Retention Job",
            description="Retention Job",
            technician_instructions=None,
            internal_notes=None,
            address_line1="123 Main St",
            address_line2=None,
            city="Dubai",
            state="Dubai",
            postal_code="00000",
            country="UAE",
            priority=JobPriority.MEDIUM,
            created_by_id=manager.id,
            created_at=now - timedelta(days=200),
            updated_at=now - timedelta(days=200),
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        update = JobUpdate(
            job_id=job.id,
            author_id=manager.id,
            message="Retention update",
            created_at=now - timedelta(days=200),
        )
        db.add(update)
        db.commit()
        db.refresh(update)

        deletable_photo = JobUpdatePhoto(
            job_update_id=update.id,
            file_key="job-updates/delete-me.jpg",
            file_name="delete-me.jpg",
            content_type="image/jpeg",
            created_at=now - timedelta(days=200),
        )
        failed_photo = JobUpdatePhoto(
            job_update_id=update.id,
            file_key="job-updates/fail-me.jpg",
            file_name="fail-me.jpg",
            content_type="image/jpeg",
            created_at=now - timedelta(days=200),
        )
        db.add_all([deletable_photo, failed_photo])
        db.commit()

        storage = StubStorageService()
        storage.failed_keys.add("job-updates/fail-me.jpg")

        summary = run_retention(db, storage_service=storage, now=now)

        remaining_keys = [photo.file_key for photo in db.query(JobUpdatePhoto).all()]
        assert summary.photo_rows_deleted == 1
        assert summary.photo_delete_failures == 1
        assert storage.deleted_keys == ["job-updates/delete-me.jpg"]
        assert remaining_keys == ["job-updates/fail-me.jpg"]


def test_retention_dry_run_reports_without_deleting(session_factory, monkeypatch):
    now = datetime(2026, 4, 17, 12, 0, tzinfo=timezone.utc)
    monkeypatch.setattr("app.services.retention.settings.LOCATION_RETENTION_DAYS", 30)
    monkeypatch.setattr("app.services.retention.settings.PRESENCE_RETENTION_DAYS", 30)
    monkeypatch.setattr("app.services.retention.settings.PHOTO_RETENTION_DAYS", 180)

    with session_factory() as db:
        technician = User(
            email="dry-run-tech@example.com",
            password_hash="hashed",
            role=UserRole.TECHNICIAN,
            technician_code="RET-003",
            full_name="Dry Run Tech",
            is_active=True,
        )
        db.add(technician)
        db.commit()
        db.refresh(technician)

        db.add(
            TechnicianPresence(
                technician_id=technician.id,
                is_logged_in=False,
                session_started_at=now - timedelta(days=45),
                last_seen_at=now - timedelta(days=45),
                updated_at=now - timedelta(days=45),
            )
        )
        db.commit()

        summary = run_retention(
            db,
            storage_service=StubStorageService(),
            now=now,
            dry_run=True,
        )

        assert summary.dry_run is True
        assert summary.presence_rows_deleted == 1
        assert db.query(TechnicianPresence).count() == 1
