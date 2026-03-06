"""Shared utility for saving skill outputs as downloadable artifact files."""

from app.core.logging import get_logger
from app.services.file_storage import file_storage_service

logger = get_logger(__name__)


async def save_skill_artifact(
    content: str,
    user_id: str | None,
    filename_hint: str,
    content_type: str = "text/markdown",
) -> dict | None:
    """Save skill output as a downloadable file.

    Args:
        content: The text content to save.
        user_id: Owner of the artifact. Skipped if None.
        filename_hint: Descriptive hint (e.g. "plan", "report"). Used for logging only;
            the actual filename is derived from the content hash by file_storage_service.
        content_type: MIME type for the file (default: text/markdown).

    Returns:
        Dict with ``download_url`` and ``storage_key``, or ``None`` on failure.
    """
    if not user_id:
        return None

    if not content:
        return None

    try:
        data = content.encode("utf-8")
        result = await file_storage_service.save_generated_image(
            image_data=data,
            user_id=user_id,
            content_type=content_type,
        )
        download_url = result.get("url", "")
        storage_key = result.get("storage_key", "")

        logger.info(
            "skill_artifact_saved",
            filename_hint=filename_hint,
            storage_key=storage_key,
            size=len(data),
        )

        return {"download_url": download_url, "storage_key": storage_key}

    except Exception as e:
        logger.warning(
            "skill_artifact_save_failed",
            filename_hint=filename_hint,
            error=str(e),
        )
        return None
