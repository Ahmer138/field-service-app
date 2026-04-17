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

### Locations

- `POST /locations/me`
- `GET /locations/technicians/{technician_id}/latest`
- `GET /locations/technicians/latest`
- `GET /locations/technicians/{technician_id}/history`

Supported location list filters:

- `include_stale`
- `q`

Supported location history filters:

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
