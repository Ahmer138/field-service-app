from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ErrorInfo(BaseModel):
    code: str
    message: str
    details: list[dict[str, Any]] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    detail: str
    error: ErrorInfo
    request_id: str | None = None
    path: str
    timestamp: datetime
