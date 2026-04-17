from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.openapi import AUTH_ERROR_RESPONSES, AUTH_LOGOUT_ERROR_RESPONSES
from app.api.rate_limit import enforce_rate_limit, get_client_ip
from app.core.config import settings
from app.core.security import create_access_token, verify_password
from app.db import get_db
from app.models import TechnicianPresence, User
from app.models.user import UserRole
from app.schemas.auth import AuthTokenRead

router = APIRouter(prefix="/auth", tags=["auth"], responses=AUTH_ERROR_RESPONSES)


@router.post(
    "/login",
    response_model=AuthTokenRead,
    summary="Log In And Issue JWT",
    description="Authenticate with email and password form fields and receive a bearer access token.",
)
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    enforce_rate_limit(
        request=request,
        scope="auth_login",
        identifier=get_client_ip(request),
        limit=settings.AUTH_LOGIN_RATE_LIMIT_COUNT,
        window_seconds=settings.AUTH_LOGIN_RATE_LIMIT_WINDOW_SECONDS,
    )

    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is inactive",
        )

    access_token = create_access_token(subject=user.email)
    return {"access_token": access_token, "token_type": "bearer"}


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=AUTH_LOGOUT_ERROR_RESPONSES,
    summary="Revoke Current Session",
    description=(
        "Invalidate the current access token for future requests. "
        "For technicians, this also marks mobile presence as logged out."
    ),
)
def logout(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    now = datetime.now(timezone.utc)
    current_user.token_revoked_before = now
    db.add(current_user)

    if current_user.role == UserRole.TECHNICIAN:
        presence = db.scalar(
            select(TechnicianPresence).where(TechnicianPresence.technician_id == current_user.id)
        )
        if presence:
            presence.is_logged_in = False
            presence.last_seen_at = now
            db.add(presence)

    db.commit()
