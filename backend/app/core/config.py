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


settings = Settings()

