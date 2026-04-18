from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central app configuration.

    We load values from environment variables, and optionally from a local `.env` file.
    This keeps secrets out of code and makes deployments consistent.
    """

    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True)

    # Local dev DB points to our Docker Postgres container (port 5432 on localhost).
    DATABASE_URL: str = "postgresql+psycopg://fsa:fsa_password@localhost:5432/fsa_db"

    # JWT configuration
    SECRET_KEY: str = "CHANGE_ME"
    SECRET_KEY_FILE: str | None = None
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # MinIO configuration for local object storage.
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minio"
    MINIO_ACCESS_KEY_FILE: str | None = None
    MINIO_SECRET_KEY: str = "minio_password"
    MINIO_SECRET_KEY_FILE: str | None = None
    MINIO_BUCKET_NAME: str = "job-update-photos"
    MINIO_SECURE: bool = False

    # A technician is considered "stale" for manager views if no location ping arrives
    # within this many minutes.
    DATABASE_URL_FILE: str | None = None
    LOCATION_STALE_AFTER_MINUTES: int = 5
    PRESENCE_ONLINE_AFTER_MINUTES: int = 2
    AUTH_LOGIN_RATE_LIMIT_COUNT: int = 5
    AUTH_LOGIN_RATE_LIMIT_WINDOW_SECONDS: int = 60
    TECHNICIAN_LOCATION_RATE_LIMIT_COUNT: int = 60
    TECHNICIAN_LOCATION_RATE_LIMIT_WINDOW_SECONDS: int = 60
    TECHNICIAN_PRESENCE_RATE_LIMIT_COUNT: int = 30
    TECHNICIAN_PRESENCE_RATE_LIMIT_WINDOW_SECONDS: int = 60
    PHOTO_UPLOAD_RATE_LIMIT_COUNT: int = 20
    PHOTO_UPLOAD_RATE_LIMIT_WINDOW_SECONDS: int = 60
    PHOTO_UPLOAD_MAX_BYTES: int = 10 * 1024 * 1024
    LOCATION_RETENTION_DAYS: int = 30
    PRESENCE_RETENTION_DAYS: int = 30
    PHOTO_RETENTION_DAYS: int = 180
    DISPLAY_TIMEZONE: str = "Asia/Dubai"
    APP_ENV: str = "development"
    SERVICE_NAME: str = "field-service-api"
    LOG_LEVEL: str = "INFO"
    METRICS_ENABLED: bool = True
    METRICS_AUTH_TOKEN: str | None = None
    TRUSTED_HOSTS: str = "localhost,127.0.0.1,testserver"
    FORWARDED_ALLOW_IPS: str = "127.0.0.1"
    ENABLE_HTTPS_REDIRECT: bool = False
    ENABLE_HSTS: bool = False
    HSTS_MAX_AGE_SECONDS: int = 31536000
    SECURITY_RESPONSE_HEADERS_ENABLED: bool = True
    CORS_ALLOWED_ORIGINS: str = (
        "http://localhost:3000,"
        "http://127.0.0.1:3000,"
        "http://localhost:5173,"
        "http://127.0.0.1:5173"
    )

    @property
    def cors_allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ALLOWED_ORIGINS.split(",") if origin.strip()]

    @property
    def trusted_hosts(self) -> list[str]:
        return [host.strip() for host in self.TRUSTED_HOSTS.split(",") if host.strip()]

    @staticmethod
    def _read_secret_file(path_value: str, setting_name: str) -> str:
        path = Path(path_value)
        if not path.is_file():
            raise RuntimeError(f"{setting_name} points to a missing file: {path}")
        value = path.read_text(encoding="utf-8").strip()
        if not value:
            raise RuntimeError(f"{setting_name} points to an empty file: {path}")
        return value

    @model_validator(mode="after")
    def apply_file_overrides(self) -> "Settings":
        file_overrides = {
            "DATABASE_URL": self.DATABASE_URL_FILE,
            "SECRET_KEY": self.SECRET_KEY_FILE,
            "MINIO_ACCESS_KEY": self.MINIO_ACCESS_KEY_FILE,
            "MINIO_SECRET_KEY": self.MINIO_SECRET_KEY_FILE,
        }
        for field_name, file_path in file_overrides.items():
            if file_path:
                setattr(
                    self,
                    field_name,
                    self._read_secret_file(file_path, f"{field_name}_FILE"),
                )
        return self

    def validate_runtime(self) -> None:
        if self.ACCESS_TOKEN_EXPIRE_MINUTES <= 0:
            raise RuntimeError("ACCESS_TOKEN_EXPIRE_MINUTES must be greater than 0")
        if self.LOCATION_STALE_AFTER_MINUTES <= 0:
            raise RuntimeError("LOCATION_STALE_AFTER_MINUTES must be greater than 0")
        if self.PRESENCE_ONLINE_AFTER_MINUTES <= 0:
            raise RuntimeError("PRESENCE_ONLINE_AFTER_MINUTES must be greater than 0")
        if self.AUTH_LOGIN_RATE_LIMIT_COUNT <= 0:
            raise RuntimeError("AUTH_LOGIN_RATE_LIMIT_COUNT must be greater than 0")
        if self.AUTH_LOGIN_RATE_LIMIT_WINDOW_SECONDS <= 0:
            raise RuntimeError("AUTH_LOGIN_RATE_LIMIT_WINDOW_SECONDS must be greater than 0")
        if self.TECHNICIAN_LOCATION_RATE_LIMIT_COUNT <= 0:
            raise RuntimeError("TECHNICIAN_LOCATION_RATE_LIMIT_COUNT must be greater than 0")
        if self.TECHNICIAN_LOCATION_RATE_LIMIT_WINDOW_SECONDS <= 0:
            raise RuntimeError("TECHNICIAN_LOCATION_RATE_LIMIT_WINDOW_SECONDS must be greater than 0")
        if self.TECHNICIAN_PRESENCE_RATE_LIMIT_COUNT <= 0:
            raise RuntimeError("TECHNICIAN_PRESENCE_RATE_LIMIT_COUNT must be greater than 0")
        if self.TECHNICIAN_PRESENCE_RATE_LIMIT_WINDOW_SECONDS <= 0:
            raise RuntimeError("TECHNICIAN_PRESENCE_RATE_LIMIT_WINDOW_SECONDS must be greater than 0")
        if self.PHOTO_UPLOAD_RATE_LIMIT_COUNT <= 0:
            raise RuntimeError("PHOTO_UPLOAD_RATE_LIMIT_COUNT must be greater than 0")
        if self.PHOTO_UPLOAD_RATE_LIMIT_WINDOW_SECONDS <= 0:
            raise RuntimeError("PHOTO_UPLOAD_RATE_LIMIT_WINDOW_SECONDS must be greater than 0")
        if self.PHOTO_UPLOAD_MAX_BYTES <= 0:
            raise RuntimeError("PHOTO_UPLOAD_MAX_BYTES must be greater than 0")
        if self.LOCATION_RETENTION_DAYS <= 0:
            raise RuntimeError("LOCATION_RETENTION_DAYS must be greater than 0")
        if self.PRESENCE_RETENTION_DAYS <= 0:
            raise RuntimeError("PRESENCE_RETENTION_DAYS must be greater than 0")
        if self.PHOTO_RETENTION_DAYS <= 0:
            raise RuntimeError("PHOTO_RETENTION_DAYS must be greater than 0")
        if not self.cors_allowed_origins:
            raise RuntimeError("CORS_ALLOWED_ORIGINS must include at least one origin")
        if not self.trusted_hosts:
            raise RuntimeError("TRUSTED_HOSTS must include at least one host")
        if not self.SERVICE_NAME.strip():
            raise RuntimeError("SERVICE_NAME must not be empty")
        if self.HSTS_MAX_AGE_SECONDS <= 0:
            raise RuntimeError("HSTS_MAX_AGE_SECONDS must be greater than 0")
        try:
            ZoneInfo(self.DISPLAY_TIMEZONE)
        except ZoneInfoNotFoundError as exc:
            raise RuntimeError(f"DISPLAY_TIMEZONE is invalid: {self.DISPLAY_TIMEZONE}") from exc
        if self.LOG_LEVEL.upper() not in {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}:
            raise RuntimeError(f"LOG_LEVEL is invalid: {self.LOG_LEVEL}")

        if self.APP_ENV.lower() in {"production", "staging"}:
            insecure_values = {"CHANGE_ME", "CHANGE_ME_TO_A_LONG_RANDOM_STRING"}
            if self.SECRET_KEY in insecure_values or len(self.SECRET_KEY) < 32:
                raise RuntimeError(
                    "SECRET_KEY must be replaced with a strong production secret in staging/production"
                )
            if "*" in self.trusted_hosts:
                raise RuntimeError(
                    "TRUSTED_HOSTS cannot contain '*' in staging/production"
                )


settings = Settings()

