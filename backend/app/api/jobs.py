from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .deps import get_current_user, require_manager_or_admin, require_technician
from ..db import get_db
from ..models import Job, JobAssignment, JobEvent, JobUpdate as JobUpdateModel, JobUpdatePhoto, User
from ..models.job import JobStatus
from ..models.job_event import JobEventType
from ..models.user import UserRole
from ..services import storage_service
from app.schemas.job import (
    JobAssignRequest,
    JobAssignmentRead,
    JobCreate,
    JobEventRead,
    JobRead,
    JobUpdate,
    JobUpdateCreate,
    JobUpdatePhotoDownload,
    JobUpdatePhotoRead,
    JobUpdateRead,
)

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _ensure_job_access(db: Session, job_id: int, current_user: User) -> Job:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    if current_user.role in (UserRole.MANAGER, UserRole.ADMIN):
        return job

    is_assigned = db.scalar(
        select(JobAssignment.id).where(
            JobAssignment.job_id == job_id,
            JobAssignment.technician_id == current_user.id,
        )
    )
    if not is_assigned:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this job")
    return job


def _ensure_job_update_access(
    db: Session,
    job_id: int,
    update_id: int,
    current_user: User,
) -> JobUpdateModel:
    _ensure_job_access(db, job_id, current_user)
    job_update = db.get(JobUpdateModel, update_id)
    if not job_update or job_update.job_id != job_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job update not found")
    return job_update


@router.post("", response_model=JobRead, status_code=status.HTTP_201_CREATED)
def create_job(
    payload: JobCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_or_admin),
):
    job = Job(
        title=payload.title,
        description=payload.description,
        technician_instructions=payload.technician_instructions,
        internal_notes=payload.internal_notes,
        address_line1=payload.address_line1,
        address_line2=payload.address_line2,
        city=payload.city,
        state=payload.state,
        postal_code=payload.postal_code,
        country=payload.country,
        scheduled_start=payload.scheduled_start,
        scheduled_end=payload.scheduled_end,
        priority=payload.priority,
        created_by_id=current_user.id,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@router.get("", response_model=list[JobRead])
def list_jobs(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role in (UserRole.MANAGER, UserRole.ADMIN):
        jobs = db.scalars(
            select(Job).order_by(Job.created_at.desc()).offset(offset).limit(limit)
        ).all()
        return jobs

    jobs = db.scalars(
        select(Job)
        .join(JobAssignment, JobAssignment.job_id == Job.id)
        .where(JobAssignment.technician_id == current_user.id)
        .order_by(Job.created_at.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return jobs


@router.get("/{job_id}", response_model=JobRead)
def get_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _ensure_job_access(db, job_id, current_user)


@router.patch("/{job_id}", response_model=JobRead)
def update_job(
    job_id: int,
    payload: JobUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_manager_or_admin),
):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(job, field, value)

    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@router.post("/{job_id}/assignments", response_model=JobAssignmentRead, status_code=status.HTTP_201_CREATED)
def assign_technician(
    job_id: int,
    payload: JobAssignRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_or_admin),
):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    technician = db.get(User, payload.technician_id)
    if not technician:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Technician not found")
    if technician.role != UserRole.TECHNICIAN:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User is not a technician")

    existing = db.scalar(
        select(JobAssignment).where(
            JobAssignment.job_id == job_id,
            JobAssignment.technician_id == payload.technician_id,
        )
    )
    if existing:
        return existing

    assignment = JobAssignment(
        job_id=job_id,
        technician_id=payload.technician_id,
        assigned_by_id=current_user.id,
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return assignment


@router.get("/{job_id}/assignments", response_model=list[JobAssignmentRead])
def list_assignments(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_job_access(db, job_id, current_user)
    assignments = db.scalars(
        select(JobAssignment)
        .where(JobAssignment.job_id == job_id)
        .order_by(JobAssignment.assigned_at.desc())
    ).all()
    return assignments


@router.post("/{job_id}/check-in", response_model=JobEventRead, status_code=status.HTTP_201_CREATED)
def check_in(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_technician),
):
    job = _ensure_job_access(db, job_id, current_user)

    event = JobEvent(job_id=job.id, actor_id=current_user.id, event_type=JobEventType.CHECK_IN)
    if job.status == JobStatus.NOT_STARTED:
        job.status = JobStatus.IN_PROGRESS

    db.add(event)
    db.add(job)
    db.commit()
    db.refresh(event)
    return event


@router.post("/{job_id}/check-out", response_model=JobEventRead, status_code=status.HTTP_201_CREATED)
def check_out(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_technician),
):
    job = _ensure_job_access(db, job_id, current_user)

    event = JobEvent(job_id=job.id, actor_id=current_user.id, event_type=JobEventType.CHECK_OUT)
    if job.status != JobStatus.COMPLETED:
        job.status = JobStatus.COMPLETED

    db.add(event)
    db.add(job)
    db.commit()
    db.refresh(event)
    return event


@router.get("/{job_id}/events", response_model=list[JobEventRead])
def list_events(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_job_access(db, job_id, current_user)
    events = db.scalars(
        select(JobEvent).where(JobEvent.job_id == job_id).order_by(JobEvent.occurred_at.desc())
    ).all()
    return events


@router.post("/{job_id}/updates", response_model=JobUpdateRead, status_code=status.HTTP_201_CREATED)
def create_update(
    job_id: int,
    payload: JobUpdateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_job_access(db, job_id, current_user)
    update = JobUpdateModel(job_id=job_id, author_id=current_user.id, message=payload.message)
    db.add(update)
    db.commit()
    db.refresh(update)
    return update


@router.get("/{job_id}/updates", response_model=list[JobUpdateRead])
def list_updates(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_job_access(db, job_id, current_user)
    updates = db.scalars(
        select(JobUpdateModel)
        .where(JobUpdateModel.job_id == job_id)
        .order_by(JobUpdateModel.created_at.desc())
    ).all()
    return updates


@router.post(
    "/{job_id}/updates/{update_id}/photos",
    response_model=JobUpdatePhotoRead,
    status_code=status.HTTP_201_CREATED,
)
def upload_update_photo(
    job_id: int,
    update_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job_update = _ensure_job_update_access(db, job_id, update_id, current_user)
    file_key = storage_service.upload_job_update_photo(file)

    photo = JobUpdatePhoto(
        job_update_id=job_update.id,
        file_key=file_key,
        file_name=file.filename,
        content_type=file.content_type,
    )
    db.add(photo)
    db.commit()
    db.refresh(photo)
    return photo


@router.get("/{job_id}/updates/{update_id}/photos", response_model=list[JobUpdatePhotoRead])
def list_update_photos(
    job_id: int,
    update_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job_update = _ensure_job_update_access(db, job_id, update_id, current_user)
    photos = db.scalars(
        select(JobUpdatePhoto)
        .where(JobUpdatePhoto.job_update_id == job_update.id)
        .order_by(JobUpdatePhoto.created_at.desc())
    ).all()
    return photos


@router.get(
    "/{job_id}/updates/{update_id}/photos/{photo_id}/download",
    response_model=JobUpdatePhotoDownload,
)
def get_update_photo_download(
    job_id: int,
    update_id: int,
    photo_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job_update = _ensure_job_update_access(db, job_id, update_id, current_user)
    photo = db.get(JobUpdatePhoto, photo_id)
    if not photo or photo.job_update_id != job_update.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found")

    return JobUpdatePhotoDownload(
        file_key=photo.file_key,
        download_url=storage_service.get_download_url(photo.file_key),
        expires_in_seconds=3600,
    )


@router.delete(
    "/{job_id}/updates/{update_id}/photos/{photo_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_update_photo(
    job_id: int,
    update_id: int,
    photo_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job_update = _ensure_job_update_access(db, job_id, update_id, current_user)
    photo = db.get(JobUpdatePhoto, photo_id)
    if not photo or photo.job_update_id != job_update.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found")

    storage_service.delete_object(photo.file_key)
    db.delete(photo)
    db.commit()
