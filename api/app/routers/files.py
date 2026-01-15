"""Router for file upload management."""

import uuid
from io import BytesIO
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, get_current_user
from app.core.logging import get_logger
from app.db.base import get_db
from app.db.models import File as FileModel
from app.services.file_processor import file_processor
from app.services.file_storage import ALLOWED_FILE_TYPES, file_storage_service

logger = get_logger(__name__)

router = APIRouter(prefix="/files")


@router.get("/supported-types")
async def get_supported_types():
    """Get list of supported file types and their limits."""
    return {
        "types": [
            {
                "mime_type": mime,
                "extensions": config["ext"],
                "max_size_mb": config["max_size"] // (1024 * 1024),
            }
            for mime, config in ALLOWED_FILE_TYPES.items()
        ]
    }


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Upload a file to storage."""

    # Read file content
    content = await file.read()
    file_size = len(content)

    # Validate file
    is_valid, error = file_storage_service.validate_file(
        filename=file.filename or "unknown",
        content_type=file.content_type or "application/octet-stream",
        file_size=file_size,
    )

    if not is_valid:
        raise HTTPException(status_code=400, detail=error)

    # Upload to R2
    file_data = BytesIO(content)

    try:
        upload_result = await file_storage_service.upload_file(
            file_data=file_data,
            user_id=current_user.id,
            original_filename=file.filename or "unknown",
            content_type=file.content_type or "application/octet-stream",
        )
    except Exception as e:
        logger.error("upload_failed", error=str(e), user_id=current_user.id)
        raise HTTPException(status_code=500, detail="Failed to upload file")

    # Extract text content for LLM context
    file_data.seek(0)
    extracted_text = await file_processor.extract_text(
        file_data=file_data,
        content_type=file.content_type or "application/octet-stream",
        filename=file.filename or "unknown",
    )

    # Check if file already exists in database (deduplication)
    result = await db.execute(
        select(FileModel).where(FileModel.storage_key == upload_result["storage_key"])
    )
    file_record = result.scalar_one_or_none()

    if not file_record:
        # Save to database if it doesn't exist
        file_record = FileModel(
            id=upload_result["file_id"],
            user_id=current_user.id,
            original_filename=file.filename or "unknown",
            content_type=file.content_type or "application/octet-stream",
            file_size=file_size,
            file_hash=upload_result.get("file_hash"),  # SHA256 content hash for deduplication
            storage_key=upload_result["storage_key"],  # Full path: user_id/hash.ext
            storage_bucket=upload_result["bucket"],
            extracted_text=extracted_text,
            extraction_status="completed" if extracted_text else "not_applicable",
        )
        db.add(file_record)
        await db.commit()
        await db.refresh(file_record)
    else:
        logger.info(
            "file_record_already_exists",
            file_id=file_record.id,
            storage_key=file_record.storage_key,
        )

    # Generate presigned URL for preview/download
    presigned_url = await file_storage_service.get_presigned_url(
        file_record.storage_key
    )

    return {
        "id": file_record.id,
        "filename": file_record.original_filename,
        "content_type": file_record.content_type,
        "file_size": file_record.file_size,
        "preview_url": presigned_url,
        "created_at": file_record.created_at.isoformat(),
    }


@router.get("/{file_id}")
async def get_file(
    file_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Get file metadata and presigned URL."""

    result = await db.execute(
        select(FileModel).where(
            FileModel.id == file_id,
            FileModel.user_id == current_user.id,
        )
    )
    file_record = result.scalar_one_or_none()

    if not file_record:
        raise HTTPException(status_code=404, detail="File not found")

    # Generate presigned URL for download
    presigned_url = await file_storage_service.get_presigned_url(
        file_record.storage_key
    )

    return {
        "id": file_record.id,
        "filename": file_record.original_filename,
        "content_type": file_record.content_type,
        "file_size": file_record.file_size,
        "download_url": presigned_url,
        "created_at": file_record.created_at.isoformat(),
    }


@router.delete("/{file_id}")
async def delete_file(
    file_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Delete a file."""

    result = await db.execute(
        select(FileModel).where(
            FileModel.id == file_id,
            FileModel.user_id == current_user.id,
        )
    )
    file_record = result.scalar_one_or_none()

    if not file_record:
        raise HTTPException(status_code=404, detail="File not found")

    # Delete from R2
    await file_storage_service.delete_file(file_record.storage_key)

    # Delete from database
    await db.delete(file_record)
    await db.commit()

    return {"status": "deleted", "file_id": file_id}


@router.get("/download/{storage_key:path}")
async def download_file(
    storage_key: str,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Download a file by storage key (for local storage backend)."""

    logger.info("download_file_request", storage_key=storage_key, user_id=current_user.id)

    # Find file by storage key
    result = await db.execute(
        select(FileModel).where(
            FileModel.storage_key == storage_key,
            FileModel.user_id == current_user.id,
        )
    )
    file_record = result.scalar_one_or_none()

    if not file_record:
        logger.error("download_file_not_found", storage_key=storage_key, user_id=current_user.id)
        raise HTTPException(status_code=404, detail="File not found")

    # Download file from storage
    try:
        logger.info("download_file_from_storage", storage_key=storage_key)
        file_data = await file_storage_service.download_file(storage_key)

        # Encode filename for Content-Disposition header (RFC 5987)
        # Use both filename (ASCII fallback) and filename* (UTF-8 encoded)
        ascii_filename = file_record.original_filename.encode("ascii", "ignore").decode("ascii")
        encoded_filename = quote(file_record.original_filename)

        content_disposition = f'inline; filename="{ascii_filename}"; filename*=UTF-8\'\'{encoded_filename}'

        logger.info("download_file_success", storage_key=storage_key, filename=file_record.original_filename)
        return StreamingResponse(
            file_data,
            media_type=file_record.content_type,
            headers={"Content-Disposition": content_disposition}
        )
    except FileNotFoundError as e:
        logger.error("download_file_not_found_on_disk", error=str(e), storage_key=storage_key)
        raise HTTPException(status_code=404, detail="File not found on storage")
    except Exception as e:
        logger.error("download_failed", error=str(e), storage_key=storage_key, error_type=type(e).__name__)
        raise HTTPException(status_code=500, detail=f"Failed to download file: {str(e)}")
