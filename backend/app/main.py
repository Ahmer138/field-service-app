import logging
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.auth import router as auth_router
from app.api.jobs import router as jobs_router
from app.api.locations import router as locations_router
from app.api.presence import router as presence_router
from app.api.users import router as users_router
from app.core.config import settings
from app.core.logging import configure_logging, log_event, reset_request_id, set_request_id
from app.db import get_db
from app.services import storage_service

settings.validate_runtime()
configure_logging(settings.LOG_LEVEL)
request_logger = logging.getLogger("app.request")

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
