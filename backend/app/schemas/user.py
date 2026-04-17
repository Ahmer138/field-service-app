from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, field_serializer, field_validator, model_validator

from ..models.user import UserRole
from .datetime_utils import normalize_for_display


class UserCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "email": "tech1@example.com",
                    "password": "secret123",
                    "role": "technician",
                    "technician_code": "DXB-101",
                    "full_name": "Tech One",
                    "is_active": True,
                },
                {
                    "email": "manager@example.com",
                    "password": "secret123",
                    "role": "manager",
                    "full_name": "Dispatch Manager",
                    "is_active": True,
                },
            ]
        }
    )

    email: EmailStr
    password: str
    role: UserRole
    technician_code: str | None = None
    full_name: str
    is_active: bool = True

    @field_validator("technician_code")
    @classmethod
    def normalize_technician_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @model_validator(mode="after")
    def validate_technician_code_rules(self) -> "UserCreate":
        if self.role == UserRole.TECHNICIAN and not self.technician_code:
            raise ValueError("Technician code is required for technicians")
        if self.role != UserRole.TECHNICIAN and self.technician_code is not None:
            raise ValueError("Technician code is only allowed for technicians")
        return self


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

    @field_serializer("created_at", "updated_at")
    def serialize_datetime(self, value: datetime) -> datetime:
        return normalize_for_display(value)
