from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import Settings


FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


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


def test_settings_reject_non_positive_rate_limit_values():
    settings = Settings(
        AUTH_LOGIN_RATE_LIMIT_COUNT=0,
        SECRET_KEY="a" * 40,
        DATABASE_URL="postgresql+psycopg://fsa:fsa_password@localhost:5432/fsa_db",
    )

    with pytest.raises(RuntimeError, match="AUTH_LOGIN_RATE_LIMIT_COUNT must be greater than 0"):
        settings.validate_runtime()


def test_settings_reject_non_positive_photo_upload_limit():
    settings = Settings(
        PHOTO_UPLOAD_MAX_BYTES=0,
        SECRET_KEY="a" * 40,
        DATABASE_URL="postgresql+psycopg://fsa:fsa_password@localhost:5432/fsa_db",
    )

    with pytest.raises(RuntimeError, match="PHOTO_UPLOAD_MAX_BYTES must be greater than 0"):
        settings.validate_runtime()


def test_settings_reject_non_positive_retention_values():
    settings = Settings(
        LOCATION_RETENTION_DAYS=0,
        SECRET_KEY="a" * 40,
        DATABASE_URL="postgresql+psycopg://fsa:fsa_password@localhost:5432/fsa_db",
    )

    with pytest.raises(RuntimeError, match="LOCATION_RETENTION_DAYS must be greater than 0"):
        settings.validate_runtime()


def test_settings_can_load_secrets_from_files():
    settings = Settings(
        SECRET_KEY="CHANGE_ME",
        SECRET_KEY_FILE=str(FIXTURES_DIR / "secret_key.txt"),
        DATABASE_URL="postgresql+psycopg://placeholder",
        DATABASE_URL_FILE=str(FIXTURES_DIR / "database_url.txt"),
        MINIO_ACCESS_KEY="placeholder",
        MINIO_ACCESS_KEY_FILE=str(FIXTURES_DIR / "minio_access_key.txt"),
        MINIO_SECRET_KEY="placeholder",
        MINIO_SECRET_KEY_FILE=str(FIXTURES_DIR / "minio_secret_key.txt"),
    )

    assert settings.SECRET_KEY == "a" * 40
    assert settings.DATABASE_URL == "postgresql+psycopg://file-user:file-pass@db:5432/file_db"
    assert settings.MINIO_ACCESS_KEY == "file-minio-user"
    assert settings.MINIO_SECRET_KEY == "file-minio-password"


def test_settings_reject_missing_secret_file():
    missing_secret_path = FIXTURES_DIR / "missing_secret.txt"

    with pytest.raises(RuntimeError, match="SECRET_KEY_FILE points to a missing file"):
        Settings(
            SECRET_KEY_FILE=str(missing_secret_path),
            SECRET_KEY="CHANGE_ME",
            DATABASE_URL="postgresql+psycopg://fsa:fsa_password@localhost:5432/fsa_db",
        )


def test_production_settings_accept_secret_key_file():
    settings = Settings(
        APP_ENV="production",
        SECRET_KEY="CHANGE_ME",
        SECRET_KEY_FILE=str(FIXTURES_DIR / "secret_key_prod.txt"),
        DATABASE_URL="postgresql+psycopg://fsa:fsa_password@localhost:5432/fsa_db",
    )

    settings.validate_runtime()


def test_production_settings_reject_wildcard_trusted_hosts():
    settings = Settings(
        APP_ENV="production",
        SECRET_KEY="a" * 40,
        DATABASE_URL="postgresql+psycopg://fsa:fsa_password@localhost:5432/fsa_db",
        TRUSTED_HOSTS="*",
    )

    with pytest.raises(RuntimeError, match="TRUSTED_HOSTS cannot contain '\\*'"):
        settings.validate_runtime()


def test_settings_reject_empty_trusted_hosts():
    settings = Settings(
        SECRET_KEY="a" * 40,
        DATABASE_URL="postgresql+psycopg://fsa:fsa_password@localhost:5432/fsa_db",
        TRUSTED_HOSTS="",
    )

    with pytest.raises(RuntimeError, match="TRUSTED_HOSTS must include at least one host"):
        settings.validate_runtime()
