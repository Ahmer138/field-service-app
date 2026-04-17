from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .deps import get_current_user, require_manager_or_admin
from .openapi import USERS_ERROR_RESPONSES
from ..core.security import get_password_hash
from ..db import get_db
from ..models import User
from ..models.user import UserRole
from app.schemas.user import UserCreate, UserListResponse, UserRead

router = APIRouter(prefix="/users", tags=["users"], responses=USERS_ERROR_RESPONSES)


@router.post(
    "",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create User",
    description="Create a manager, admin, or technician account. Manager/admin access required.",
)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_manager_or_admin),
):
    existing = db.scalar(select(User).where(User.email == payload.email))
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already exists")

    if payload.technician_code:
        existing_technician_code = db.scalar(
            select(User).where(User.technician_code == payload.technician_code)
        )
        if existing_technician_code:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Technician code already exists",
            )

    user = User(
        email=payload.email,
        password_hash=get_password_hash(payload.password),
        role=payload.role,
        technician_code=payload.technician_code,
        full_name=payload.full_name,
        is_active=payload.is_active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get(
    "",
    response_model=UserListResponse,
    summary="List Users",
    description=(
        "List users with optional role, active-state, and free-text filtering. "
        "Returns a paginated response envelope."
    ),
)
def list_users(
    role: UserRole | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    q: str | None = Query(default=None, min_length=1),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_manager_or_admin),
):
    stmt = select(User)
    if role is not None:
        stmt = stmt.where(User.role == role)
    if is_active is not None:
        stmt = stmt.where(User.is_active == is_active)
    if q:
        term = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                User.email.ilike(term),
                User.full_name.ilike(term),
                User.technician_code.ilike(term),
            )
        )

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    users = db.scalars(stmt.order_by(User.created_at.desc()).offset(offset).limit(limit)).all()
    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "items": users,
    }


@router.get(
    "/me",
    response_model=UserRead,
    summary="Get Current User",
    description="Return the currently authenticated user profile.",
)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user
