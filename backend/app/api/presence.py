from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .deps import require_manager_or_admin, require_technician
from ..core.config import settings
from ..db import get_db
from ..models import TechnicianLocation, TechnicianPresence, User
from ..models.user import UserRole
from ..schemas.location import TechnicianLocationRead
from ..schemas.presence import TechnicianPresenceListResponse, TechnicianPresenceRead

router = APIRouter(prefix="/presence", tags=["presence"])


def _normalize_to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _presence_is_online(presence: TechnicianPresence) -> bool:
    if not presence.is_logged_in:
        return False
    threshold = timedelta(minutes=settings.PRESENCE_ONLINE_AFTER_MINUTES)
    return datetime.now(timezone.utc) - _normalize_to_utc(presence.last_seen_at) <= threshold


def _get_latest_locations_for_technicians(
    db: Session,
    technician_ids: list[int],
) -> dict[int, TechnicianLocation]:
    if not technician_ids:
        return {}

    locations = db.scalars(
        select(TechnicianLocation)
        .where(TechnicianLocation.technician_id.in_(technician_ids))
        .order_by(
            TechnicianLocation.technician_id.asc(),
            TechnicianLocation.recorded_at.desc(),
            TechnicianLocation.id.desc(),
        )
    ).all()

    latest_by_technician: dict[int, TechnicianLocation] = {}
    for location in locations:
        latest_by_technician.setdefault(location.technician_id, location)
    return latest_by_technician


def _serialize_presence(
    presence: TechnicianPresence,
    technician: User,
    latest_location: TechnicianLocation | None,
) -> TechnicianPresenceRead:
    return TechnicianPresenceRead(
        technician_id=presence.technician_id,
        technician_name=technician.full_name,
        is_logged_in=presence.is_logged_in,
        is_online=_presence_is_online(presence),
        session_started_at=presence.session_started_at,
        last_seen_at=presence.last_seen_at,
        latest_location=TechnicianLocationRead.model_validate(latest_location) if latest_location else None,
    )


@router.post(
    "/me/heartbeat",
    response_model=TechnicianPresenceRead,
    status_code=status.HTTP_201_CREATED,
    summary="Send Presence Heartbeat",
    description="Technician endpoint that marks the mobile session as active and updates last-seen time.",
)
def heartbeat_presence(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_technician),
):
    now = datetime.now(timezone.utc)
    presence = db.scalar(
        select(TechnicianPresence).where(TechnicianPresence.technician_id == current_user.id)
    )
    if presence is None:
        presence = TechnicianPresence(
            technician_id=current_user.id,
            is_logged_in=True,
            session_started_at=now,
            last_seen_at=now,
        )
        db.add(presence)
    else:
        if not presence.is_logged_in:
            presence.session_started_at = now
        presence.is_logged_in = True
        presence.last_seen_at = now
        db.add(presence)

    db.commit()
    db.refresh(presence)
    latest_location = db.scalar(
        select(TechnicianLocation)
        .where(TechnicianLocation.technician_id == current_user.id)
        .order_by(TechnicianLocation.recorded_at.desc(), TechnicianLocation.id.desc())
        .limit(1)
    )
    return _serialize_presence(presence, current_user, latest_location)


@router.post(
    "/me/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Log Out Technician Presence",
    description="Technician endpoint that marks the mobile session as logged out.",
)
def logout_presence(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_technician),
):
    presence = db.scalar(
        select(TechnicianPresence).where(TechnicianPresence.technician_id == current_user.id)
    )
    if presence:
        presence.is_logged_in = False
        presence.last_seen_at = datetime.now(timezone.utc)
        db.add(presence)
        db.commit()


@router.get(
    "/technicians/{technician_id}",
    response_model=TechnicianPresenceRead,
    summary="Get Technician Presence",
    description="Manager/admin endpoint returning one technician's current session and online/offline presence state.",
)
def get_technician_presence(
    technician_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_manager_or_admin),
):
    technician = db.get(User, technician_id)
    if not technician or technician.role != UserRole.TECHNICIAN:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Technician not found")

    presence = db.scalar(
        select(TechnicianPresence).where(TechnicianPresence.technician_id == technician_id)
    )
    if not presence:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Presence not found")

    latest_location = _get_latest_locations_for_technicians(db, [technician_id]).get(technician_id)
    return _serialize_presence(presence, technician, latest_location)


@router.get(
    "/technicians",
    response_model=TechnicianPresenceListResponse,
    summary="List Technician Presence",
    description=(
        "Manager/admin endpoint listing technician presence with optional offline "
        "filtering, name search, and pagination. Returns a paginated response envelope."
    ),
)
def list_technician_presence(
    include_offline: bool = Query(True),
    q: str | None = Query(default=None, min_length=1),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_manager_or_admin),
):
    presences = db.scalars(
        select(TechnicianPresence).order_by(
            TechnicianPresence.is_logged_in.desc(),
            TechnicianPresence.last_seen_at.desc(),
        )
    ).all()
    if not presences:
        return []

    technician_ids = [presence.technician_id for presence in presences]
    technicians = db.scalars(select(User).where(User.id.in_(technician_ids))).all()
    technicians_by_id = {technician.id: technician for technician in technicians}
    latest_locations = _get_latest_locations_for_technicians(db, technician_ids)

    payload = [
        _serialize_presence(
            presence,
            technicians_by_id[presence.technician_id],
            latest_locations.get(presence.technician_id),
        )
        for presence in presences
    ]
    if not include_offline:
        payload = [presence for presence in payload if presence.is_online]
    if q:
        term = q.strip().lower()
        payload = [
            presence
            for presence in payload
            if term in presence.technician_name.lower()
        ]

    payload.sort(key=lambda presence: (presence.is_online, presence.last_seen_at), reverse=True)
    total = len(payload)
    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "items": payload[offset : offset + limit],
    }
