from __future__ import annotations

from datetime import datetime, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db import get_db
from app.models import User
from app.models.user import UserRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def _normalize_to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _issued_at_from_claim(raw_iat: object) -> datetime | None:
    if isinstance(raw_iat, (int, float)):
        return datetime.fromtimestamp(raw_iat, tz=timezone.utc)
    if isinstance(raw_iat, str):
        try:
            parsed = datetime.fromisoformat(raw_iat)
        except ValueError:
            return None
        return _normalize_to_utc(parsed)
    if isinstance(raw_iat, datetime):
        return _normalize_to_utc(raw_iat)
    return None


def get_current_token_payload(token: str = Depends(oauth2_scheme)) -> dict:
    payload = decode_access_token(token)
    if not payload or not payload.get("sub"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )
    return payload


def get_current_user(
    token_payload: dict = Depends(get_current_token_payload),
    db: Session = Depends(get_db),
) -> User:
    subject = token_payload["sub"]
    user = db.query(User).filter(User.email == subject).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is inactive",
        )
    token_issued_at = _issued_at_from_claim(token_payload.get("issued_at")) or _issued_at_from_claim(
        token_payload.get("iat")
    )
    if token_issued_at is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )
    if user.token_revoked_before and token_issued_at <= _normalize_to_utc(user.token_revoked_before):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has been revoked",
        )
    return user


def require_manager_or_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in (UserRole.MANAGER, UserRole.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    return current_user


def require_technician(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.TECHNICIAN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Technician role required",
        )
    return current_user
