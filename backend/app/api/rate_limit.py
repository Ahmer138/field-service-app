from __future__ import annotations

from fastapi import HTTPException, Request, status

from app.services import rate_limiter

RATE_LIMIT_EXCEEDED_MESSAGE = "Rate limit exceeded. Try again later."


def get_client_ip(request: Request) -> str:
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def enforce_rate_limit(
    *,
    request: Request,
    scope: str,
    identifier: str,
    limit: int,
    window_seconds: int,
) -> None:
    retry_after = rate_limiter.check(
        scope=scope,
        identifier=identifier,
        limit=limit,
        window_seconds=window_seconds,
    )
    if retry_after is None:
        return

    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=RATE_LIMIT_EXCEEDED_MESSAGE,
        headers={"Retry-After": str(retry_after)},
    )
