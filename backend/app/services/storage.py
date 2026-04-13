from __future__ import annotations

from uuid import uuid4

from minio import Minio

from app.core.config import settings


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
        if not self.client.bucket_exists(self.bucket_name):
            self.client.make_bucket(self.bucket_name)

    def upload_job_update_photo(self, upload_file) -> str:
        self.ensure_bucket()

        safe_name = upload_file.filename or "upload.bin"
        object_key = f"job-updates/{uuid4()}-{safe_name}"

        self.client.put_object(
            self.bucket_name,
            object_key,
            data=upload_file.file,
            length=-1,
            part_size=10 * 1024 * 1024,
            content_type=upload_file.content_type or "application/octet-stream",
        )
        return object_key


storage_service = ObjectStorageService()