from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class AuthTokenRead(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.example.token",
                "token_type": "bearer",
            }
        }
    )

    access_token: str
    token_type: str
