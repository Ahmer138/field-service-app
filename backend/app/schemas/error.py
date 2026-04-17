from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ErrorInfo(BaseModel):
    code: str
    message: str
    details: list[dict[str, Any]] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "detail": "Insufficient permissions",
                "error": {
                    "code": "forbidden",
                    "message": "Insufficient permissions",
                    "details": [],
                },
                "request_id": "4c4d6d8e2c3648c38fd2b0f03b649f31",
                "path": "/users",
                "timestamp": "2026-04-17T09:30:00Z",
            }
        }
    )

    detail: str
    error: ErrorInfo
    request_id: str | None = None
    path: str
    timestamp: datetime
