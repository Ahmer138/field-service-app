from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .deps import get_current_user, require_manager_or_admin, require_technician
from ..db import get_db
from ..models import TechnicianLocation, User
from ..models.user import UserRole
from ..schemas.location import TechnicianLocationCreate, TechnicianLocationRead

router = APIRouter(prefix="/locations", tags=["locations"])


@router.post("/me", response_model=TechnicianLocationRead, status_code=status.HTTP_201_CREATED)
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
    response_model=TechnicianLocationRead,
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
    return location


@router.get("/technicians/latest", response_model=list[TechnicianLocationRead])
def list_latest_technician_locations(
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

    return list(latest_by_technician.values())
