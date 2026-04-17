from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .deps import get_current_user, require_manager_or_admin, require_technician
from ..core.config import settings
from ..db import get_db
from ..models import TechnicianLocation, User
from ..models.user import UserRole
from ..schemas.location import (
    TechnicianLocationCreate,
    TechnicianLocationHistoryResponse,
    TechnicianLocationLatestListResponse,
    TechnicianLocationLatestRead,
    TechnicianLocationRead,
)

router = APIRouter(prefix="/locations", tags=["locations"])


def _normalize_recorded_at(recorded_at: datetime) -> datetime:
    if recorded_at.tzinfo is None:
        return recorded_at.replace(tzinfo=timezone.utc)
    return recorded_at.astimezone(timezone.utc)


def _location_is_stale(recorded_at: datetime) -> bool:
    stale_after = timedelta(minutes=settings.LOCATION_STALE_AFTER_MINUTES)
    return datetime.now(timezone.utc) - _normalize_recorded_at(recorded_at) > stale_after


def _serialize_latest_location(location: TechnicianLocation, technician: User) -> TechnicianLocationLatestRead:
    return TechnicianLocationLatestRead(
        id=location.id,
        technician_id=location.technician_id,
        latitude=location.latitude,
        longitude=location.longitude,
        accuracy_meters=location.accuracy_meters,
        recorded_at=location.recorded_at,
        created_at=location.created_at,
        technician_name=technician.full_name,
        is_stale=_location_is_stale(location.recorded_at),
    )


@router.post(
    "/me",
    response_model=TechnicianLocationRead,
    status_code=status.HTTP_201_CREATED,
    summary="Send Technician Location Ping",
    description="Technician endpoint for reporting the device GPS location while logged into the mobile app.",
)
def create_location_ping(
    payload: TechnicianLocationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_technician),
):
    location = TechnicianLocation(
        technician_id=current_user.id,
        latitude=payload.latitude,
        longitude=payload.longitude,
        accuracy_meters=payload.accuracy_meters,
        recorded_at=payload.recorded_at or datetime.now(timezone.utc),
    )
    db.add(location)
    db.commit()
    db.refresh(location)
    return location


@router.get(
    "/technicians/{technician_id}/latest",
    response_model=TechnicianLocationLatestRead,
    summary="Get Latest Technician Location",
    description="Manager/admin endpoint for the latest known location of one technician.",
)
def get_latest_technician_location(
    technician_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_manager_or_admin),
):
    technician = db.get(User, technician_id)
    if not technician or technician.role != UserRole.TECHNICIAN:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Technician not found")

    location = db.scalar(
        select(TechnicianLocation)
        .where(TechnicianLocation.technician_id == technician_id)
        .order_by(TechnicianLocation.recorded_at.desc(), TechnicianLocation.id.desc())
        .limit(1)
    )
    if not location:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")
    return _serialize_latest_location(location, technician)


@router.get(
    "/technicians/latest",
    response_model=TechnicianLocationLatestListResponse,
    summary="List Latest Technician Locations",
    description=(
        "Manager/admin endpoint returning the latest location per technician, "
        "with stale filtering, name search, and pagination. Returns a paginated response envelope."
    ),
)
def list_latest_technician_locations(
    include_stale: bool = Query(True),
    q: str | None = Query(default=None, min_length=1),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_manager_or_admin),
):
    locations = db.scalars(
        select(TechnicianLocation).order_by(
            TechnicianLocation.technician_id.asc(),
            TechnicianLocation.recorded_at.desc(),
            TechnicianLocation.id.desc(),
        )
    ).all()

    latest_by_technician: dict[int, TechnicianLocation] = {}
    for location in locations:
        latest_by_technician.setdefault(location.technician_id, location)

    technicians = db.scalars(
        select(User).where(User.id.in_(latest_by_technician.keys()))
    ).all()
    technicians_by_id = {technician.id: technician for technician in technicians}

    latest_locations = [
        _serialize_latest_location(location, technicians_by_id[location.technician_id])
        for location in latest_by_technician.values()
    ]
    if not include_stale:
        latest_locations = [location for location in latest_locations if not location.is_stale]
    if q:
        term = q.strip().lower()
        latest_locations = [
            location
            for location in latest_locations
            if term in location.technician_name.lower()
        ]

    latest_locations.sort(key=lambda location: location.recorded_at, reverse=True)
    total = len(latest_locations)
    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "items": latest_locations[offset : offset + limit],
    }


@router.get(
    "/technicians/{technician_id}/history",
    response_model=TechnicianLocationHistoryResponse,
    summary="Get Technician Location History",
    description=(
        "Manager/admin endpoint for filtered location history of a technician. "
        "Returns a paginated response envelope."
    ),
)
def get_technician_location_history(
    technician_id: int,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    recorded_from: datetime | None = Query(default=None),
    recorded_to: datetime | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(require_manager_or_admin),
):
    technician = db.get(User, technician_id)
    if not technician or technician.role != UserRole.TECHNICIAN:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Technician not found")

    stmt = select(TechnicianLocation).where(TechnicianLocation.technician_id == technician_id)
    if recorded_from is not None:
        stmt = stmt.where(TechnicianLocation.recorded_at >= recorded_from)
    if recorded_to is not None:
        stmt = stmt.where(TechnicianLocation.recorded_at <= recorded_to)

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = db.scalars(
        stmt.order_by(TechnicianLocation.recorded_at.desc(), TechnicianLocation.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "items": items,
    }
