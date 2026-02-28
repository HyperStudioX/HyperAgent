"""Usage API endpoint for token and cost tracking."""

from fastapi import APIRouter, Depends, Query

from app.core.auth import CurrentUser, get_current_user
from app.services.usage_tracker import get_usage_summary

router = APIRouter(prefix="/usage", tags=["usage"])


@router.get("/")
async def get_usage(
    conversation_id: str | None = Query(default=None, description="Filter by conversation ID"),
    user_id: str | None = Query(default=None, description="Filter by user ID"),
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Get aggregated usage statistics.

    Returns total token counts, costs, and breakdowns by model and tier.
    Optionally filtered by conversation_id or user_id.
    """
    summary = get_usage_summary(
        conversation_id=conversation_id,
        user_id=user_id,
    )
    return summary
