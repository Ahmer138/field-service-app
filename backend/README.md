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

4. Update any secrets in `.env` for local development only.
   Important settings include:

- `DISPLAY_TIMEZONE=Asia/Dubai`
- `CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173`

For staging/production, prefer mounted secret files outside the repo over storing real secrets in `.env`.

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

## Secrets Management

Local development can continue using `.env`, but deployment environments should supply secrets outside the repo.

Supported file-based secret settings:

- `DATABASE_URL_FILE`
- `SECRET_KEY_FILE`
- `MINIO_ACCESS_KEY_FILE`
- `MINIO_SECRET_KEY_FILE`

If both a direct value and a `*_FILE` variant are set, the file value wins.

Example deployment pattern:

1. Mount secret files into the container, such as `/run/secrets/secret_key`.
2. Set the matching `*_FILE` environment variables to those mounted paths.
3. Keep real production secrets out of committed `.env` files.

Example:

```text
SECRET_KEY_FILE=/run/secrets/secret_key
DATABASE_URL_FILE=/run/secrets/database_url
MINIO_ACCESS_KEY_FILE=/run/secrets/minio_access_key
MINIO_SECRET_KEY_FILE=/run/secrets/minio_secret_key
```

## Observability

The backend now exposes Prometheus-style metrics at `GET /metrics` and continues to emit structured JSON logs to stdout for aggregation.

Relevant settings:

- `SERVICE_NAME`
- `LOG_LEVEL`
- `METRICS_ENABLED`
- `METRICS_AUTH_TOKEN`

Metrics behavior:

- `METRICS_ENABLED=true` exposes the scrape endpoint
- if `METRICS_AUTH_TOKEN` is set, scrapers must send `Authorization: Bearer <token>`
- request metrics include counts, latency histogram buckets, error totals, and rate-limited totals
- dependency health is exported after `GET /health/db` and `GET /health/storage` checks run

Example metrics scrape:

```powershell
curl http://localhost:8000/metrics
```

Example authenticated scrape:

```powershell
curl -H "Authorization: Bearer my-metrics-token" http://localhost:8000/metrics
```

Suggested alerts:

- elevated `5xx` responses from `field_service_http_requests_total`
- spikes in `field_service_rate_limited_requests_total`
- sustained latency growth in `field_service_http_request_duration_seconds`
- `field_service_dependency_health_status{component="database"}` dropping to `0`
- `field_service_dependency_health_status{component="storage"}` dropping to `0`

Log aggregation guidance:

- ship stdout logs to your central log platform such as ELK, OpenSearch, Loki, or Cloud logging
- index `service`, `environment`, `request_id`, `event`, `path`, and `status_code`
- use `request_id` to correlate API failures with application and proxy logs

## Backup and Recovery

The backend now includes Docker Compose backup and restore scripts plus a recovery runbook.

Files:

- [BACKUP_RECOVERY.md](BACKUP_RECOVERY.md)
- `.\scripts\backup-compose.ps1`
- `.\scripts\restore-compose.ps1`

Backup behavior:

- captures PostgreSQL as a logical `pg_dump` archive
- captures MinIO object data from `/data`
- writes a `backup-manifest.json` with the captured Alembic version and restore order

Create a backup:

```powershell
.\scripts\backup-compose.ps1
```

Restore a backup:

```powershell
.\scripts\restore-compose.ps1 -BackupPath .\backups\20260418T120000Z
```

Operational guidance:

- store backup sets outside the Docker host after creation
- run restore drills regularly in a separate environment
- verify `/health/db`, `/health/storage`, login, and photo access after restore
- keep multiple recovery points instead of a single latest backup

## Client Handoff

Frontend and mobile teams should use [CLIENT_AUTH_SESSION_GUIDE.md](CLIENT_AUTH_SESSION_GUIDE.md) as the current source of truth for:

- login request format and bearer token usage
- logout and token revocation behavior
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

## Retention Policy

The backend now includes a config-driven retention task for location history, presence data, and stored job-update photos.

Default retention windows:

- `LOCATION_RETENTION_DAYS=30`
- `PRESENCE_RETENTION_DAYS=30`
- `PHOTO_RETENTION_DAYS=180`

Current behavior:

- deletes technician location history older than the configured cutoff
- keeps the latest location row for each technician even if it is older than the cutoff
- deletes stale technician presence rows older than the configured cutoff
- deletes old photo metadata and object storage files older than the configured cutoff

Run a dry run:

```powershell
.\.venv\Scripts\python -m app.tasks.retention --dry-run
```

Run the actual cleanup:

```powershell
.\.venv\Scripts\python -m app.tasks.retention
```

The command prints a JSON summary and returns a non-zero exit code if any photo object deletions fail.

## Logging

The API emits structured JSON request logs and includes an `X-Request-ID` response header for traceability.

Relevant settings:

- `SERVICE_NAME`
- `LOG_LEVEL`
- `DISPLAY_TIMEZONE`
- `DATABASE_URL_FILE`
- `SECRET_KEY_FILE`
- `AUTH_LOGIN_RATE_LIMIT_COUNT`
- `AUTH_LOGIN_RATE_LIMIT_WINDOW_SECONDS`
- `MINIO_ACCESS_KEY_FILE`
- `MINIO_SECRET_KEY_FILE`
- `METRICS_ENABLED`
- `METRICS_AUTH_TOKEN`
- `TECHNICIAN_LOCATION_RATE_LIMIT_COUNT`
- `TECHNICIAN_LOCATION_RATE_LIMIT_WINDOW_SECONDS`
- `TECHNICIAN_PRESENCE_RATE_LIMIT_COUNT`
- `TECHNICIAN_PRESENCE_RATE_LIMIT_WINDOW_SECONDS`
- `PHOTO_UPLOAD_RATE_LIMIT_COUNT`
- `PHOTO_UPLOAD_RATE_LIMIT_WINDOW_SECONDS`
- `LOCATION_RETENTION_DAYS`
- `PRESENCE_RETENTION_DAYS`
- `PHOTO_RETENTION_DAYS`

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
- `POST /auth/logout`

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

- HTTPS and reverse proxy hardening

## Frontend Integration Note

The API uses configurable CORS via `CORS_ALLOWED_ORIGINS`. Update that value for your web frontend domains before deployment.
