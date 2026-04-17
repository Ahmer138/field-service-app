from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

from minio import Minio

from app.core.config import settings


class StorageServiceError(Exception):
    pass


class ObjectStorageService:
    def __init__(self) -> None:
        self.client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )
        self.bucket_name = settings.MINIO_BUCKET_NAME

    def ensure_bucket(self) -> None:
        try:
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
        except Exception as exc:
            raise StorageServiceError("Storage service is unavailable") from exc

    def is_available(self) -> bool:
        try:
            return self.client.bucket_exists(self.bucket_name)
        except Exception:
            return False

    def upload_job_update_photo(self, upload_file) -> str:
        self.ensure_bucket()

        safe_name = upload_file.filename or "upload.bin"
        object_key = f"job-updates/{uuid4()}-{safe_name}"

        try:
            self.client.put_object(
                self.bucket_name,
                object_key,
                data=upload_file.file,
                length=-1,
                part_size=10 * 1024 * 1024,
                content_type=upload_file.content_type or "application/octet-stream",
            )
        except Exception as exc:
            raise StorageServiceError("Failed to upload photo to object storage") from exc
        return object_key

    def get_download_url(self, object_key: str, expires_seconds: int = 3600) -> str:
        self.ensure_bucket()
        try:
            return self.client.presigned_get_object(
                self.bucket_name,
                object_key,
                expires=timedelta(seconds=expires_seconds),
            )
        except Exception as exc:
            raise StorageServiceError("Failed to generate download URL") from exc

    def delete_object(self, object_key: str) -> None:
        self.ensure_bucket()
        try:
            self.client.remove_object(self.bucket_name, object_key)
        except Exception as exc:
            raise StorageServiceError("Failed to delete photo from object storage") from exc


storage_service = ObjectStorageService()
