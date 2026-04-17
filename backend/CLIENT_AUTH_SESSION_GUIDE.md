# Client Auth and Session Guide

This document is the backend handoff for web and mobile clients.
It describes the current authentication, session, GPS, presence, pagination, and error contracts implemented in the API today.

## Current Auth Model

- Authentication uses a JWT bearer access token.
- The backend currently issues only an access token.
- There is no refresh token flow yet.
- `POST /auth/logout` revokes all tokens previously issued for that user up to the logout time.
- Inactive users are blocked at login and on authenticated requests.

Current token settings:

- `JWT_ALGORITHM=HS256`
- `ACCESS_TOKEN_EXPIRE_MINUTES=60`

## Login Request

Endpoint:

- `POST /auth/login`

Request format:

- Content type must be `application/x-www-form-urlencoded`
- The backend uses OAuth2 password form parsing
- `username` must contain the user's email address
- `password` must contain the plain-text password

Example request:

```http
POST /auth/login HTTP/1.1
Content-Type: application/x-www-form-urlencoded

username=manager@example.com&password=Secret123!
```

Example success response:

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.example.token",
  "token_type": "bearer"
}
```

Login failure behavior:

- invalid email or password returns `401`
- inactive user returns `403`
- repeated attempts can return `429`

Current login rate limit:

- `AUTH_LOGIN_RATE_LIMIT_COUNT=5`
- `AUTH_LOGIN_RATE_LIMIT_WINDOW_SECONDS=60`

## Using the Access Token

Authenticated endpoints require:

```http
Authorization: Bearer <access_token>
```

Recommended client behavior:

- Web app: keep the access token in the least persistent storage you can support safely for the current architecture.
- Mobile app: store the access token in OS-protected secure storage.
- On app boot or page refresh, call `GET /users/me` to validate the token and rebuild the signed-in user state.
- If any request returns `401`, treat the token as unusable and force re-login.
- If any request returns `403` with inactive-user or permission errors, do not retry blindly.

Important current limitation:

- There is still no refresh token flow yet.
- Logout is currently implemented as a revoke-before timestamp on the user, so previously issued tokens for that user stop working after logout.
- A client logout should still clear the stored token locally.

## Recommended Session Flows

### Web Manager/Admin

1. Submit email and password to `POST /auth/login`.
2. Save the returned access token.
3. Immediately call `GET /users/me`.
4. Use the access token on all subsequent requests.
5. On explicit logout, call `POST /auth/logout` and then clear local session state.
6. On `401`, clear local session state and redirect to login.

### Mobile Technician

1. Submit email and password to `POST /auth/login`.
2. Save the returned access token in secure storage.
3. Call `GET /users/me` and confirm the user role is `technician`.
4. Start presence heartbeat and GPS reporting only while the technician is logged into the app.
5. On technician logout, call `POST /auth/logout` and then clear the local token.
6. On `401`, stop heartbeat and GPS reporting and force re-login.

## Technician Presence Contract

Technician session presence is tracked separately from JWT issuance, but auth logout now also drives presence logout for technicians.

Endpoints:

- `POST /auth/logout`
- `POST /presence/me/heartbeat`
- `POST /presence/me/logout`

Current behavior:

- The first heartbeat creates a presence record if none exists.
- Heartbeat sets `is_logged_in=true`.
- If the technician was previously logged out, heartbeat resets `session_started_at`.
- Heartbeat always updates `last_seen_at`.
- `POST /presence/me/logout` sets `is_logged_in=false` and updates `last_seen_at`.
- `POST /auth/logout` revokes the current authenticated session and also marks technician presence logged out.

Manager/admin visibility:

- `GET /presence/technicians/{technician_id}`
- `GET /presence/technicians`

Online/offline behavior:

- A technician is considered online only if `is_logged_in=true`
- And the last heartbeat is within `PRESENCE_ONLINE_AFTER_MINUTES`
- Current default: `PRESENCE_ONLINE_AFTER_MINUTES=2`

Current heartbeat rate limit:

- `TECHNICIAN_PRESENCE_RATE_LIMIT_COUNT=30`
- `TECHNICIAN_PRESENCE_RATE_LIMIT_WINDOW_SECONDS=60`

Client guidance:

- A heartbeat every `30` to `60` seconds is safe against the current limit and sufficient for live presence.
- Do not send rapid heartbeat bursts when the app resumes.
- If the app is logged out, stop sending heartbeats.

## Technician GPS Contract

Technicians are tracked while logged into the mobile app.

Endpoint:

- `POST /locations/me`

Example request body:

```json
{
  "latitude": 25.2048,
  "longitude": 55.2708,
  "accuracy_meters": 12.5,
  "recorded_at": "2026-04-20T08:15:00+04:00"
}
```

Current behavior:

- The endpoint requires an authenticated technician token.
- If `recorded_at` is omitted, the server uses current UTC time.
- Managers/admins can view latest location and location history.
- Latest-location views include an `is_stale` flag.

Manager/admin location views:

- `GET /locations/technicians/{technician_id}/latest`
- `GET /locations/technicians/latest`
- `GET /locations/technicians/{technician_id}/history`

Current location rate limit:

- `TECHNICIAN_LOCATION_RATE_LIMIT_COUNT=60`
- `TECHNICIAN_LOCATION_RATE_LIMIT_WINDOW_SECONDS=60`

Client guidance:

- Send location only while the technician is logged into the app.
- A cadence around every `30` to `60` seconds is reasonable under the current limit.
- Include `accuracy_meters` when available so manager views can judge signal quality.

## User-Facing Timezone Rules

Product rule implemented in backend:

- User-facing manager/admin timestamps are normalized to `Asia/Dubai` (`UTC+04:00`)

This currently applies to manager-visible location and presence responses.

Client guidance:

- Do not re-interpret these values as raw UTC when rendering manager/admin screens.
- Preserve the provided offset in UI formatting.
- If the client converts times again, convert from the provided offset-aware timestamp.

## Pagination Contract

Manager-facing list endpoints use a paginated envelope:

```json
{
  "total": 125,
  "offset": 0,
  "limit": 50,
  "items": []
}
```

Supported list endpoints:

- `GET /users`
- `GET /jobs`
- `GET /locations/technicians/latest`
- `GET /locations/technicians/{technician_id}/history`
- `GET /presence/technicians`

Client guidance:

- Use `offset` and `limit` as request query parameters where supported.
- Treat `total` as the full filtered count.
- Use `items.length` only for the current page size.

## Standard Error Contract

Errors use a consistent envelope:

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

Client guidance:

- `detail` is retained for backward compatibility.
- Prefer `error.code` for UI branching and retry behavior.
- Include `request_id` in support tooling and bug reports.

Common status handling:

- `400` validation or business-rule failure
- `401` invalid or expired authentication
- `403` inactive user or insufficient permissions
- `404` resource not found
- `413` oversized photo upload
- `429` rate limited, honor `Retry-After`
- `503` temporary storage/backend dependency issue

## Request Tracing

The backend includes an `X-Request-ID` response header on every request.

Client guidance:

- Log the response `X-Request-ID` for failed requests.
- A client may also send its own `X-Request-ID` request header if it wants to correlate logs end-to-end.

## CORS and Frontend Origins

Web frontend access is controlled by `CORS_ALLOWED_ORIGINS`.

Current local defaults include:

- `http://localhost:3000`
- `http://127.0.0.1:3000`
- `http://localhost:5173`
- `http://127.0.0.1:5173`

If the frontend host changes, update backend configuration before testing in browser environments.

## Known Backend Gaps Still Pending

These are not solved by the current auth/session flow:

- device-specific session management beyond the current user-wide logout cutoff
- production secrets management outside local `.env`
- monitoring, alerting, and centralized logs
- backup and recovery posture
- HTTPS and reverse-proxy hardening
