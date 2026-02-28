"""Router for persistent memory management."""

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.auth import CurrentUser, get_current_user
from app.core.logging import get_logger
from app.services.memory_service import ALL_MEMORY_TYPES, get_memory_store

logger = get_logger(__name__)

router = APIRouter(prefix="/memory")


@router.get("")
async def get_memories(
    type: str | None = Query(None, description="Filter by memory type"),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Get memories for the current user, optionally filtered by type."""
    if type and type not in ALL_MEMORY_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid memory type. Must be one of: {', '.join(ALL_MEMORY_TYPES)}",
        )

    store = get_memory_store()
    memories = await store.get_memories_async(
        current_user.id, memory_type=type
    )
    return {
        "memories": [
            {
                "id": m.id,
                "type": m.memory_type,
                "content": m.content,
                "metadata": m.metadata,
                "created_at": m.created_at,
                "access_count": m.access_count,
            }
            for m in memories
        ]
    }


@router.delete("/{memory_id}")
async def delete_memory(
    memory_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Delete a specific memory."""
    store = get_memory_store()
    deleted = await store.delete_memory_async(current_user.id, memory_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"success": True}
