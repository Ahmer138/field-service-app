# Backend Checklist

This file tracks what is complete and what remains for the Field Service App backend.

## Complete

- JWT auth and inactive-user blocking
- user create/list/me flows
- jobs, assignments, check-in/check-out, events, updates, and photos
- image-only photo validation and storage health
- technician GPS tracking, latest location, history, stale detection
- technician mobile presence heartbeat/logout and manager/admin visibility
- manager-facing filters across users, jobs, locations, and presence
- UAE-local timestamp normalization for manager-facing responses
- structured JSON request logging with `X-Request-ID`
- startup config validation and configurable CORS
- Docker, Compose, Alembic migrations, `.env.example`, and README
- automated pytest suite
- basic GitHub Actions CI for test execution

## Must-Have Before Frontend Handoff

- [x] bounded pagination on manager list endpoints
- [x] paginated response envelopes with `total`, `offset`, `limit`, and `items`
- [x] standardized API error response shape across all endpoints
- [x] OpenAPI examples for paginated list responses
- [x] frontend-facing auth/session guidance for web and mobile clients

## Must-Have Before Beta

- [x] type-check and lint steps in CI
- [x] migration smoke check in CI
- [x] request rate limiting for login and other abuse-sensitive endpoints
- [x] upload size limits and clearer storage failure handling
- [ ] retention policy for technician location history, presence data, and photos

## Must-Have Before Production

- [ ] refresh-token or token revocation strategy for mobile sessions
- [ ] secrets management outside `.env`
- [ ] monitoring, alerting, and log aggregation
- [ ] backup and recovery posture for PostgreSQL and object storage
- [ ] HTTPS/reverse proxy and deployment hardening
