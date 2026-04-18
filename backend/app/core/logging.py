from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar, Token
from datetime import datetime, timezone
from typing import Any

_request_id_context: ContextVar[str | None] = ContextVar("request_id", default=None)
_logging_configured = False
_service_name = "app"
_environment = "development"


def configure_logging(level_name: str, *, service_name: str, environment: str) -> None:
    global _logging_configured
    global _service_name
    global _environment

    level = getattr(logging, level_name.upper(), logging.INFO)
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    _service_name = service_name
    _environment = environment

    if _logging_configured:
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))

    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    _logging_configured = True


def set_request_id(request_id: str) -> Token[str | None]:
    return _request_id_context.set(request_id)


def reset_request_id(token: Token[str | None]) -> None:
    _request_id_context.reset(token)


def get_request_id() -> str | None:
    return _request_id_context.get()


def _normalize_value(value: Any) -> Any:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat()
    return value


def log_event(logger: logging.Logger, level: int, event: str, **fields: Any) -> None:
    payload: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": logging.getLevelName(level).lower(),
        "logger": logger.name,
        "service": _service_name,
        "environment": _environment,
        "event": event,
    }

    request_id = fields.pop("request_id", None) or get_request_id()
    if request_id is not None:
        payload["request_id"] = request_id

    for key, value in fields.items():
        if value is not None:
            payload[key] = _normalize_value(value)

    logger.log(level, json.dumps(payload, sort_keys=True))
