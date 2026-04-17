from __future__ import annotations

import pytest

from app.core.config import Settings


def test_production_settings_reject_placeholder_secret():
    settings = Settings(
        APP_ENV="production",
        SECRET_KEY="CHANGE_ME",
        DATABASE_URL="postgresql+psycopg://fsa:fsa_password@localhost:5432/fsa_db",
    )

    with pytest.raises(RuntimeError, match="SECRET_KEY must be replaced"):
        settings.validate_runtime()


def test_settings_reject_invalid_display_timezone():
    settings = Settings(
        DISPLAY_TIMEZONE="Invalid/Timezone",
        SECRET_KEY="a" * 40,
        DATABASE_URL="postgresql+psycopg://fsa:fsa_password@localhost:5432/fsa_db",
    )

    with pytest.raises(RuntimeError, match="DISPLAY_TIMEZONE is invalid"):
        settings.validate_runtime()


def test_settings_reject_invalid_log_level():
    settings = Settings(
        LOG_LEVEL="verbose",
        SECRET_KEY="a" * 40,
        DATABASE_URL="postgresql+psycopg://fsa:fsa_password@localhost:5432/fsa_db",
    )

    with pytest.raises(RuntimeError, match="LOG_LEVEL is invalid"):
        settings.validate_runtime()
