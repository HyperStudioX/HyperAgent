"""File storage service supporting both R2 (production) and local filesystem (development)."""

import hashlib
import os
import shutil
import uuid
from io import BytesIO
from pathlib import Path
from typing import BinaryIO

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Supported file types and their MIME types
ALLOWED_FILE_TYPES = {
    # Documents
    "application/pdf": {"ext": [".pdf"], "max_size": 50 * 1024 * 1024},  # 50MB
    "application/msword": {"ext": [".doc"], "max_size": 25 * 1024 * 1024},
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": {
        "ext": [".docx"],
        "max_size": 25 * 1024 * 1024,
    },
    "text/plain": {"ext": [".txt", ".md"], "max_size": 10 * 1024 * 1024},
    "text/markdown": {"ext": [".md"], "max_size": 10 * 1024 * 1024},
    # Spreadsheets
    "application/vnd.ms-excel": {"ext": [".xls"], "max_size": 25 * 1024 * 1024},
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {
        "ext": [".xlsx"],
        "max_size": 25 * 1024 * 1024,
    },
    "text/csv": {"ext": [".csv"], "max_size": 10 * 1024 * 1024},
    # Images
    "image/png": {"ext": [".png"], "max_size": 20 * 1024 * 1024},
    "image/jpeg": {"ext": [".jpg", ".jpeg"], "max_size": 20 * 1024 * 1024},
    "image/gif": {"ext": [".gif"], "max_size": 10 * 1024 * 1024},
    "image/webp": {"ext": [".webp"], "max_size": 20 * 1024 * 1024},
    # Code files
    "text/x-python": {"ext": [".py"], "max_size": 5 * 1024 * 1024},
    "text/javascript": {"ext": [".js", ".jsx"], "max_size": 5 * 1024 * 1024},
    "application/typescript": {"ext": [".ts", ".tsx"], "max_size": 5 * 1024 * 1024},
    "application/json": {"ext": [".json"], "max_size": 10 * 1024 * 1024},
    "text/html": {"ext": [".html", ".htm"], "max_size": 5 * 1024 * 1024},
    "text/css": {"ext": [".css"], "max_size": 5 * 1024 * 1024},
}

DEFAULT_MAX_FILE_SIZE = 25 * 1024 * 1024  # 25MB default


class FileStorageService:
    """Service for managing file uploads (supports R2 and local filesystem)."""

    def __init__(self):
        self._client = None
        self.backend = settings.storage_backend

        if self.backend == "local":
            # Ensure local storage directory exists
            os.makedirs(settings.local_storage_path, exist_ok=True)
            logger.info("storage_backend", backend="local", path=settings.local_storage_path)
        else:
            logger.info("storage_backend", backend="r2", bucket=settings.r2_bucket_name)

    @property
    def client(self):
        """Lazy initialization of S3 client (only for R2 backend)."""
        if self.backend != "r2":
            return None

        if self._client is None:
            try:
                import boto3
                self._client = boto3.client(
                    "s3",
                    endpoint_url=settings.r2_endpoint_url,
                    aws_access_key_id=settings.r2_access_key_id,
                    aws_secret_access_key=settings.r2_secret_access_key,
                    region_name="auto",
                )
            except Exception as e:
                logger.error("s3_client_init_failed", error=str(e))
                raise
        return self._client

    def validate_file(
        self, filename: str, content_type: str, file_size: int
    ) -> tuple[bool, str | None]:
        """Validate file type and size.

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check content type
        if content_type not in ALLOWED_FILE_TYPES:
            return False, f"File type '{content_type}' is not allowed"

        # Check file size
        max_size = ALLOWED_FILE_TYPES[content_type].get(
            "max_size", DEFAULT_MAX_FILE_SIZE
        )
        if file_size > max_size:
            return (
                False,
                f"File size exceeds limit of {max_size // (1024 * 1024)}MB",
            )

        return True, None

    def _calculate_file_hash(self, file_data: BinaryIO) -> str:
        """Calculate SHA256 hash of file content."""
        sha256_hash = hashlib.sha256()

        # Read file in chunks to handle large files efficiently
        file_data.seek(0)
        for byte_block in iter(lambda: file_data.read(4096), b""):
            sha256_hash.update(byte_block)

        # Reset file pointer
        file_data.seek(0)
        return sha256_hash.hexdigest()

    async def upload_file(
        self,
        file_data: BinaryIO,
        user_id: str,
        original_filename: str,
        content_type: str,
    ) -> dict:
        """Upload a file to storage (R2 or local filesystem).

        Files are stored using content-based hashing for deduplication and security.
        Storage structure: {user_id}/{file_hash}{extension}

        Returns:
            Dict with storage_key, file_hash, and metadata
        """
        # Calculate content hash
        file_hash = self._calculate_file_hash(file_data)

        # Extract file extension
        file_id = str(uuid.uuid4())
        ext = Path(original_filename).suffix.lower()

        # Storage key: user_id/file_hash.ext (content-addressable)
        storage_key = f"{user_id}/{file_hash}{ext}"

        if self.backend == "local":
            return await self._upload_local(file_data, storage_key, file_id, file_hash, user_id, original_filename)
        else:
            return await self._upload_r2(file_data, storage_key, content_type, file_id, file_hash, user_id, original_filename)

    async def _upload_local(
        self, file_data: BinaryIO, storage_key: str, file_id: str, file_hash: str, user_id: str, original_filename: str
    ) -> dict:
        """Upload file to local filesystem."""
        try:
            # Create directory structure
            file_path = Path(settings.local_storage_path) / storage_key
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # Check if file already exists (deduplication)
            if file_path.exists():
                logger.info(
                    "file_already_exists",
                    storage_key=storage_key,
                    file_hash=file_hash,
                    user_id=user_id,
                    filename=original_filename,
                )
            else:
                # Write file
                with open(file_path, "wb") as f:
                    shutil.copyfileobj(file_data, f)

                logger.info(
                    "file_uploaded_local",
                    storage_key=storage_key,
                    file_hash=file_hash,
                    user_id=user_id,
                    filename=original_filename,
                )

            return {
                "file_id": file_id,
                "storage_key": storage_key,
                "file_hash": file_hash,
                "bucket": "local",
            }

        except Exception as e:
            logger.error("file_upload_failed_local", error=str(e))
            raise

    async def _upload_r2(
        self, file_data: BinaryIO, storage_key: str, content_type: str, file_id: str, file_hash: str, user_id: str, original_filename: str
    ) -> dict:
        """Upload file to R2 storage."""
        try:
            from botocore.exceptions import ClientError

            # Check if file already exists (deduplication)
            try:
                self.client.head_object(
                    Bucket=settings.r2_bucket_name,
                    Key=storage_key,
                )
                logger.info(
                    "file_already_exists_r2",
                    storage_key=storage_key,
                    file_hash=file_hash,
                    user_id=user_id,
                    filename=original_filename,
                )
            except ClientError as e:
                if e.response['Error']['Code'] == '404':
                    # File doesn't exist, upload it
                    self.client.upload_fileobj(
                        file_data,
                        settings.r2_bucket_name,
                        storage_key,
                        ExtraArgs={
                            "ContentType": content_type,
                            "Metadata": {
                                "user_id": user_id,
                                "original_filename": original_filename,
                                "file_hash": file_hash,
                            },
                        },
                    )

                    logger.info(
                        "file_uploaded_r2",
                        storage_key=storage_key,
                        file_hash=file_hash,
                        user_id=user_id,
                        filename=original_filename,
                    )
                else:
                    raise

            return {
                "file_id": file_id,
                "storage_key": storage_key,
                "file_hash": file_hash,
                "bucket": settings.r2_bucket_name,
            }

        except ClientError as e:
            logger.error("file_upload_failed_r2", error=str(e))
            raise

    async def get_presigned_url(
        self, storage_key: str, expires_in: int = 3600
    ) -> str:
        """Generate a presigned URL for file access (R2 only)."""
        if self.backend == "local":
            # For local files, return a file path or local URL
            # In production, you'd want to serve these through the API
            return f"/api/v1/files/download/{storage_key}"

        return self.client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": settings.r2_bucket_name,
                "Key": storage_key,
            },
            ExpiresIn=expires_in,
        )

    async def delete_file(self, storage_key: str) -> bool:
        """Delete a file from storage."""
        try:
            if self.backend == "local":
                file_path = Path(settings.local_storage_path) / storage_key
                if file_path.exists():
                    file_path.unlink()
                logger.info("file_deleted_local", storage_key=storage_key)
            else:
                from botocore.exceptions import ClientError
                self.client.delete_object(
                    Bucket=settings.r2_bucket_name,
                    Key=storage_key,
                )
                logger.info("file_deleted_r2", storage_key=storage_key)
            return True
        except Exception as e:
            logger.error("file_delete_failed", error=str(e), backend=self.backend)
            return False

    async def download_file(self, storage_key: str) -> BytesIO:
        """Download a file from storage."""
        buffer = BytesIO()

        if self.backend == "local":
            file_path = Path(settings.local_storage_path) / storage_key
            with open(file_path, "rb") as f:
                shutil.copyfileobj(f, buffer)
        else:
            self.client.download_fileobj(
                settings.r2_bucket_name,
                storage_key,
                buffer,
            )

        buffer.seek(0)
        return buffer


file_storage_service = FileStorageService()
