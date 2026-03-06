"""Router for persistent memory management."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.auth import CurrentUser, get_current_user
from app.core.logging import get_logger
from app.services.memory_service import ALL_MEMORY_TYPES, get_memory_store

logger = get_logger(__name__)

router = APIRouter(prefix="/memory")


class CreateMemoryRequest(BaseModel):
    type: str = Field(..., description="Memory type: preference, fact, episodic, procedural")
    content: str = Field(..., min_length=1, max_length=2000)


class UpdateMemoryRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)


def _serialize_memory(m):
    return {
        "id": m.id,
        "type": m.memory_type,
        "content": m.content,
        "metadata": m.metadata,
        "created_at": m.created_at,
        "access_count": m.access_count,
    }


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
    return {"memories": [_serialize_memory(m) for m in memories]}


@router.post("")
async def create_memory(
    body: CreateMemoryRequest,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Create a new memory."""
    if body.type not in ALL_MEMORY_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid memory type. Must be one of: {', '.join(ALL_MEMORY_TYPES)}",
        )

    store = get_memory_store()
    entry = await store.add_memory_async(
        user_id=current_user.id,
        memory_type=body.type,
        content=body.content,
        metadata={"source_type": "manual"},
    )
    return _serialize_memory(entry)


@router.put("/{memory_id}")
async def update_memory(
    memory_id: str,
    body: UpdateMemoryRequest,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Update an existing memory's content."""
    store = get_memory_store()
    entry = await store.update_memory_async(current_user.id, memory_id, body.content)
    if entry is None:
        raise HTTPException(status_code=404, detail="Memory not found")
    return _serialize_memory(entry)


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
