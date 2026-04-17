import logging
from datetime import datetime, timezone
from time import perf_counter
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.auth import router as auth_router
from app.api.jobs import router as jobs_router
from app.api.locations import router as locations_router
from app.api.presence import router as presence_router
from app.api.users import router as users_router
from app.core.config import settings
from app.core.logging import (
    configure_logging,
    get_request_id,
    log_event,
    reset_request_id,
    set_request_id,
)
from app.db import get_db
from app.schemas.error import ErrorInfo
from app.schemas.error import ErrorResponse
from app.services import storage_service

settings.validate_runtime()
configure_logging(settings.LOG_LEVEL)
request_logger = logging.getLogger("app.request")
error_logger = logging.getLogger("app.error")

app = FastAPI(
    title="Field Service App API",
    version="0.2.0",
    summary="Backend API for dispatch, field operations, location tracking, and technician presence",
    description=(
        "Field Service App backend for managers, admins, and technicians. "
        "Supports authentication, job workflows, assignments, updates, photo uploads, "
        "technician location tracking, and mobile presence monitoring."
    ),
    openapi_tags=[
        {"name": "auth", "description": "Authentication and token issuance."},
        {"name": "users", "description": "Manager/admin user management and current-user lookup."},
        {"name": "jobs", "description": "Job lifecycle, assignments, updates, events, and photos."},
        {"name": "locations", "description": "Technician GPS location ping, latest location, and history."},
        {"name": "presence", "description": "Mobile session heartbeat, logout, and live presence views."},
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(jobs_router)
app.include_router(locations_router)
app.include_router(presence_router)
app.include_router(users_router)


def _status_code_to_error_code(status_code: int) -> str:
    return {
        status.HTTP_400_BAD_REQUEST: "bad_request",
        status.HTTP_401_UNAUTHORIZED: "unauthorized",
        status.HTTP_403_FORBIDDEN: "forbidden",
        status.HTTP_404_NOT_FOUND: "not_found",
        status.HTTP_409_CONFLICT: "conflict",
        status.HTTP_422_UNPROCESSABLE_CONTENT: "validation_error",
        status.HTTP_500_INTERNAL_SERVER_ERROR: "internal_server_error",
    }.get(status_code, "request_error")


def _error_payload(
    request: Request,
    *,
    status_code: int,
    message: str,
    details: list[dict] | None = None,
) -> dict:
    return ErrorResponse(
        detail=message,
        error=ErrorInfo(
            code=_status_code_to_error_code(status_code),
            message=message,
            details=details or [],
        ),
        request_id=get_request_id(),
        path=request.url.path,
        timestamp=datetime.now(timezone.utc),
    ).model_dump(mode="json")


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if isinstance(exc.detail, str):
        message = exc.detail
        details: list[dict] = []
    else:
        message = "Request failed"
        details = [{"detail": exc.detail}]

    return JSONResponse(
        status_code=exc.status_code,
        content=_error_payload(
            request,
            status_code=exc.status_code,
            message=message,
            details=details,
        ),
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    details = [
        {
            "loc": list(error["loc"]),
            "message": error["msg"],
            "type": error["type"],
        }
        for error in exc.errors()
    ]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content=_error_payload(
            request,
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            message="Request validation failed",
            details=details,
        ),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    log_event(
        error_logger,
        logging.ERROR,
        "unhandled_exception",
        request_id=get_request_id(),
        path=request.url.path,
        method=request.method,
        error_type=type(exc).__name__,
        error_message=str(exc),
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=_error_payload(
            request,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Internal server error",
        ),
    )


@app.middleware("http")
async def log_requests(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or uuid4().hex
    context_token = set_request_id(request_id)
    start = perf_counter()

    try:
        response = await call_next(request)
    except Exception:
        duration_ms = round((perf_counter() - start) * 1000, 2)
        log_event(
            request_logger,
            logging.ERROR,
            "request_error",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            query=request.url.query or None,
            client_ip=request.client.host if request.client else None,
            status_code=500,
            duration_ms=duration_ms,
        )
        reset_request_id(context_token)
        raise

    duration_ms = round((perf_counter() - start) * 1000, 2)
    response.headers["X-Request-ID"] = request_id
    log_event(
        request_logger,
        logging.INFO,
        "request_complete",
        request_id=request_id,
        method=request.method,
        path=request.url.path,
        query=request.url.query or None,
        client_ip=request.client.host if request.client else None,
        status_code=response.status_code,
        duration_ms=duration_ms,
    )
    reset_request_id(context_token)
    return response


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/health/db")
def health_db(db: Session = Depends(get_db)):
    """
    Database connectivity check.

    Explanation:
    - `Depends(get_db)` tells FastAPI: "for this request, call get_db() to obtain a DB session"
    - We run a trivial SQL query: SELECT 1
    - If the query succeeds, Postgres is reachable and working
    """
    db.execute(text("SELECT 1"))
    return {"db": "ok"}


@app.get("/health/storage")
def health_storage():
    return {"storage": "ok" if storage_service.is_available() else "unavailable"}
