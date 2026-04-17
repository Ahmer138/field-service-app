from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.openapi import AUTH_ERROR_RESPONSES
from app.core.security import create_access_token, verify_password
from app.db import get_db
from app.models import User
from app.schemas.auth import AuthTokenRead

router = APIRouter(prefix="/auth", tags=["auth"], responses=AUTH_ERROR_RESPONSES)


@router.post(
    "/login",
    response_model=AuthTokenRead,
    summary="Log In And Issue JWT",
    description="Authenticate with email and password form fields and receive a bearer access token.",
)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
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
