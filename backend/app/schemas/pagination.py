from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    total: int = Field(ge=0)
    offset: int = Field(ge=0)
    limit: int = Field(ge=1)
    items: list[T]
