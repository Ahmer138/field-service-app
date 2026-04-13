from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr

from ..models.user import UserRole


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    role: UserRole
    technician_code: str | None = None
    full_name: str
    is_active: bool = True


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    role: UserRole
    technician_code: str | None
    full_name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
