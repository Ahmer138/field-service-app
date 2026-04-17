# Field Service App Backend

FastAPI backend for a field service workflow with:

- JWT authentication
- user management for managers, admins, and technicians
- job creation, assignment, check-in/check-out, and updates
- job photo upload/download/delete via MinIO
- technician GPS location tracking
- technician mobile presence/heartbeat tracking

All manager-facing location and presence timestamps are configured for UAE display time via `Asia/Dubai`.

## Stack

- FastAPI
- SQLAlchemy 2.x
- Alembic
- PostgreSQL
- MinIO
- Pytest

## Local Setup

1. Create and activate a virtual environment.
2. Install dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

3. Copy the environment template:

```powershell
Copy-Item .env.example .env
```

4. Update any secrets in `.env`.
   Important settings include:

- `DISPLAY_TIMEZONE=Asia/Dubai`
- `CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173`

5. Start PostgreSQL and MinIO.

6. Run migrations:

```powershell
alembic upgrade head
```

7. Start the API:

```powershell
uvicorn app.main:app --reload
```

Open:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Docker Compose

The repo includes `docker-compose.yml` for local API + Postgres + MinIO startup.

```powershell
docker compose up --build
```

The API container runs `alembic upgrade head` before starting Uvicorn.

## Testing

Run the automated suite:

```powershell
.\.venv\Scripts\python -m pytest -q
```

## CI

The repo now includes a GitHub Actions workflow at `.github/workflows/backend-ci.yml`.
It now runs two backend quality gates on push and pull request updates:

- `python -m ruff check .`
- `python -m pyright`
- `alembic upgrade head` against disposable PostgreSQL in CI
- `python -m pytest -q`

For local developer checks:

```powershell
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
.\.venv\Scripts\python -m ruff check .
.\.venv\Scripts\python -m pyright
.\.venv\Scripts\alembic upgrade head
.\.venv\Scripts\python -m pytest -q
```

The local Alembic command requires PostgreSQL to be available and reachable from `DATABASE_URL`.

## Client Handoff

Frontend and mobile teams should use [CLIENT_AUTH_SESSION_GUIDE.md](CLIENT_AUTH_SESSION_GUIDE.md) as the current source of truth for:

- login request format and bearer token usage
- web and mobile session behavior
- technician heartbeat and GPS reporting expectations
- paginated list envelopes and standardized error responses
- UAE (`Asia/Dubai`) timestamp handling in manager-facing responses

## Pagination

Manager-facing list endpoints return a paginated envelope:

```json
{
  "total": 125,
  "offset": 0,
  "limit": 50,
  "items": []
}
```

## Error Responses

API errors now return a consistent JSON envelope while keeping `detail` for backward compatibility:

```json
{
  "detail": "Insufficient permissions",
  "error": {
    "code": "forbidden",
    "message": "Insufficient permissions",
    "details": []
  },
  "request_id": "4c4d6d8e2c3648c38fd2b0f03b649f31",
  "path": "/users",
  "timestamp": "2026-04-17T09:30:00Z"
}
```

Swagger/ReDoc now also include concrete examples for the paginated list envelopes and standardized error responses.

## Rate Limiting

Abuse-sensitive endpoints now apply configurable rate limits:

- `POST /auth/login`
- `POST /locations/me`
- `POST /presence/me/heartbeat`
- `POST /jobs/{job_id}/updates/{update_id}/photos`

Rate-limited responses return HTTP `429` with a `Retry-After` header and the standard API error envelope.

## Photo Upload Hardening

Job update photo uploads now enforce a configurable maximum size and return clearer failures when object storage is unavailable.

Relevant settings:

- `PHOTO_UPLOAD_MAX_BYTES`
- `PHOTO_UPLOAD_RATE_LIMIT_COUNT`
- `PHOTO_UPLOAD_RATE_LIMIT_WINDOW_SECONDS`

Photo upload failure behavior:

- non-image uploads return `400`
- oversized uploads return `413`
- temporary object storage failures return `503`

## Logging

The API emits structured JSON request logs and includes an `X-Request-ID` response header for traceability.

Relevant settings:

- `LOG_LEVEL`
- `DISPLAY_TIMEZONE`
- `AUTH_LOGIN_RATE_LIMIT_COUNT`
- `AUTH_LOGIN_RATE_LIMIT_WINDOW_SECONDS`
- `TECHNICIAN_LOCATION_RATE_LIMIT_COUNT`
- `TECHNICIAN_LOCATION_RATE_LIMIT_WINDOW_SECONDS`
- `TECHNICIAN_PRESENCE_RATE_LIMIT_COUNT`
- `TECHNICIAN_PRESENCE_RATE_LIMIT_WINDOW_SECONDS`
- `PHOTO_UPLOAD_RATE_LIMIT_COUNT`
- `PHOTO_UPLOAD_RATE_LIMIT_WINDOW_SECONDS`

Example request log fields:

- `event`
- `request_id`
- `method`
- `path`
- `status_code`
- `duration_ms`
- `client_ip`

## Core Endpoints

### Auth

- `POST /auth/login`

### Users

- `POST /users`
- `GET /users`
- `GET /users/me`

Supported user filters:

- `role`
- `is_active`
- `q`
- `offset`
- `limit`

### Jobs

- `POST /jobs`
- `GET /jobs`
- `GET /jobs/{job_id}`
- `PATCH /jobs/{job_id}`
- `POST /jobs/{job_id}/assignments`
- `DELETE /jobs/{job_id}/assignments/{assignment_id}`
- `POST /jobs/{job_id}/check-in`
- `POST /jobs/{job_id}/check-out`
- `GET /jobs/{job_id}/events`
- `POST /jobs/{job_id}/updates`
- `GET /jobs/{job_id}/updates`
- `POST /jobs/{job_id}/updates/{update_id}/photos`
- `GET /jobs/{job_id}/updates/{update_id}/photos`
- `GET /jobs/{job_id}/updates/{update_id}/photos/{photo_id}/download`
- `DELETE /jobs/{job_id}/updates/{update_id}/photos/{photo_id}`

Supported job filters:

- `status`
- `priority`
- `technician_id`
- `created_by_id`
- `city`
- `scheduled_start_from`
- `scheduled_start_to`
- `q`
- `offset`
- `limit`

### Locations

- `POST /locations/me`
- `GET /locations/technicians/{technician_id}/latest`
- `GET /locations/technicians/latest`
- `GET /locations/technicians/{technician_id}/history`

Supported location list filters:

- `include_stale`
- `q`
- `offset`
- `limit`

Supported location history filters:

- `offset`
- `limit`
- `recorded_from`
- `recorded_to`

### Presence

- `POST /presence/me/heartbeat`
- `POST /presence/me/logout`
- `GET /presence/technicians/{technician_id}`
- `GET /presence/technicians`

Supported presence filters:

- `include_offline`
- `q`
- `offset`
- `limit`

## Health Checks

- `GET /health`
- `GET /health/db`
- `GET /health/storage`

## Current Scope

This backend is now suitable for MVP integration, but production deployment still needs the usual infrastructure work:

- secret management
- HTTPS and reverse proxy
- monitoring/log aggregation
- backup and retention policies
- CI/CD pipeline

## Frontend Integration Note

The API uses configurable CORS via `CORS_ALLOWED_ORIGINS`. Update that value for your web frontend domains before deployment.
