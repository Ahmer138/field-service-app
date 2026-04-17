from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

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
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # MinIO configuration for local object storage.
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minio"
    MINIO_SECRET_KEY: str = "minio_password"
    MINIO_BUCKET_NAME: str = "job-update-photos"
    MINIO_SECURE: bool = False

    # A technician is considered "stale" for manager views if no location ping arrives
    # within this many minutes.
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
    DISPLAY_TIMEZONE: str = "Asia/Dubai"
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    CORS_ALLOWED_ORIGINS: str = (
        "http://localhost:3000,"
        "http://127.0.0.1:3000,"
        "http://localhost:5173,"
        "http://127.0.0.1:5173"
    )

    @property
    def cors_allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ALLOWED_ORIGINS.split(",") if origin.strip()]

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
        if not self.cors_allowed_origins:
            raise RuntimeError("CORS_ALLOWED_ORIGINS must include at least one origin")
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


settings = Settings()

