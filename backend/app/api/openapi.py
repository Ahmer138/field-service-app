from __future__ import annotations

from fastapi import status

from app.schemas.error import ErrorResponse


def build_error_response(
    status_code: int,
    description: str,
    message: str,
    *,
    code: str,
    path: str,
    details: list[dict] | None = None,
) -> dict:
    return {
        status_code: {
            "model": ErrorResponse,
            "description": description,
            "content": {
                "application/json": {
                    "example": {
                        "detail": message,
                        "error": {
                            "code": code,
                            "message": message,
                            "details": details or [],
                        },
                        "request_id": "4c4d6d8e2c3648c38fd2b0f03b649f31",
                        "path": path,
                        "timestamp": "2026-04-17T09:30:00Z",
                    }
                }
            },
        }
    }


def merge_responses(*response_maps: dict) -> dict:
    merged: dict = {}
    for response_map in response_maps:
        merged.update(response_map)
    return merged


AUTH_ERROR_RESPONSES = merge_responses(
    build_error_response(
        status.HTTP_401_UNAUTHORIZED,
        "Authentication failed.",
        "Invalid email or password",
        code="unauthorized",
        path="/auth/login",
    ),
    build_error_response(
        status.HTTP_403_FORBIDDEN,
        "Authenticated user is inactive.",
        "User is inactive",
        code="forbidden",
        path="/auth/login",
    ),
    build_error_response(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "Submitted form data failed validation.",
        "Request validation failed",
        code="validation_error",
        path="/auth/login",
        details=[
            {
                "loc": ["body", "username"],
                "message": "Field required",
                "type": "missing",
            }
        ],
    ),
    build_error_response(
        status.HTTP_429_TOO_MANY_REQUESTS,
        "Too many login attempts were made from the same client.",
        "Rate limit exceeded. Try again later.",
        code="rate_limited",
        path="/auth/login",
    ),
)


AUTH_LOGOUT_ERROR_RESPONSES = merge_responses(
    build_error_response(
        status.HTTP_401_UNAUTHORIZED,
        "Authentication is required or the current token was already revoked.",
        "Invalid authentication credentials",
        code="unauthorized",
        path="/auth/logout",
    ),
    build_error_response(
        status.HTTP_403_FORBIDDEN,
        "Authenticated user is inactive.",
        "User is inactive",
        code="forbidden",
        path="/auth/logout",
    ),
)


USERS_ERROR_RESPONSES = merge_responses(
    build_error_response(
        status.HTTP_401_UNAUTHORIZED,
        "Authentication is required.",
        "Invalid authentication credentials",
        code="unauthorized",
        path="/users",
    ),
    build_error_response(
        status.HTTP_403_FORBIDDEN,
        "Current user lacks manager/admin access.",
        "Insufficient permissions",
        code="forbidden",
        path="/users",
    ),
    build_error_response(
        status.HTTP_409_CONFLICT,
        "A unique user field already exists.",
        "Email already exists",
        code="conflict",
        path="/users",
    ),
    build_error_response(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "Request body failed validation.",
        "Request validation failed",
        code="validation_error",
        path="/users",
        details=[
            {
                "loc": ["body", "technician_code"],
                "message": "Value error, Technician code is required for technicians",
                "type": "value_error",
            }
        ],
    ),
)


JOBS_ERROR_RESPONSES = merge_responses(
    build_error_response(
        status.HTTP_400_BAD_REQUEST,
        "The request violates a workflow or business rule.",
        "Job must be in progress before check-out",
        code="bad_request",
        path="/jobs/123/check-out",
    ),
    build_error_response(
        status.HTTP_401_UNAUTHORIZED,
        "Authentication is required.",
        "Invalid authentication credentials",
        code="unauthorized",
        path="/jobs",
    ),
    build_error_response(
        status.HTTP_403_FORBIDDEN,
        "Current user does not have access to the requested resource.",
        "No access to this job",
        code="forbidden",
        path="/jobs/123",
    ),
    build_error_response(
        status.HTTP_404_NOT_FOUND,
        "The requested job or nested resource was not found.",
        "Job not found",
        code="not_found",
        path="/jobs/123",
    ),
    build_error_response(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "Query parameters or request body failed validation.",
        "Request validation failed",
        code="validation_error",
        path="/jobs",
        details=[
            {
                "loc": ["query", "limit"],
                "message": "Input should be less than or equal to 200",
                "type": "less_than_equal",
            }
        ],
    ),
    build_error_response(
        status.HTTP_429_TOO_MANY_REQUESTS,
        "Too many abuse-sensitive job actions were attempted in a short time window.",
        "Rate limit exceeded. Try again later.",
        code="rate_limited",
        path="/jobs/123/updates/55/photos",
    ),
    build_error_response(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        "Object storage is temporarily unavailable.",
        "Photo storage is temporarily unavailable",
        code="request_error",
        path="/jobs/123/updates/55/photos",
    ),
)


LOCATIONS_ERROR_RESPONSES = merge_responses(
    build_error_response(
        status.HTTP_401_UNAUTHORIZED,
        "Authentication is required.",
        "Invalid authentication credentials",
        code="unauthorized",
        path="/locations/technicians/latest",
    ),
    build_error_response(
        status.HTTP_403_FORBIDDEN,
        "Current user does not have the required role.",
        "Insufficient permissions",
        code="forbidden",
        path="/locations/technicians/latest",
    ),
    build_error_response(
        status.HTTP_404_NOT_FOUND,
        "The requested technician or location was not found.",
        "Location not found",
        code="not_found",
        path="/locations/technicians/7/latest",
    ),
    build_error_response(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "Query parameters or request body failed validation.",
        "Request validation failed",
        code="validation_error",
        path="/locations/me",
        details=[
            {
                "loc": ["body", "latitude"],
                "message": "Input should be less than or equal to 90",
                "type": "less_than_equal",
            }
        ],
    ),
    build_error_response(
        status.HTTP_429_TOO_MANY_REQUESTS,
        "Too many location pings were submitted in a short time window.",
        "Rate limit exceeded. Try again later.",
        code="rate_limited",
        path="/locations/me",
    ),
)


PRESENCE_ERROR_RESPONSES = merge_responses(
    build_error_response(
        status.HTTP_401_UNAUTHORIZED,
        "Authentication is required.",
        "Invalid authentication credentials",
        code="unauthorized",
        path="/presence/technicians",
    ),
    build_error_response(
        status.HTTP_403_FORBIDDEN,
        "Current user does not have the required role.",
        "Insufficient permissions",
        code="forbidden",
        path="/presence/technicians",
    ),
    build_error_response(
        status.HTTP_404_NOT_FOUND,
        "The requested technician or presence record was not found.",
        "Presence not found",
        code="not_found",
        path="/presence/technicians/7",
    ),
    build_error_response(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "Query parameters failed validation.",
        "Request validation failed",
        code="validation_error",
        path="/presence/technicians",
        details=[
            {
                "loc": ["query", "offset"],
                "message": "Input should be greater than or equal to 0",
                "type": "greater_than_equal",
            }
        ],
    ),
    build_error_response(
        status.HTTP_429_TOO_MANY_REQUESTS,
        "Too many presence heartbeats were submitted in a short time window.",
        "Rate limit exceeded. Try again later.",
        code="rate_limited",
        path="/presence/me/heartbeat",
    ),
)
