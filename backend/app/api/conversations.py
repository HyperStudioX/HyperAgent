"""Router for conversation management."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, get_current_user
from app.core.logging import get_logger
from app.db.base import get_db
from app.models.schemas import (
    ConversationListResponse,
    ConversationMessageResponse,
    ConversationResponse,
    CreateConversationRequest,
    CreateMessageRequest,
    UpdateConversationRequest,
    UpdateMessageRequest,
)
from app.repository import conversation_repository

logger = get_logger(__name__)

router = APIRouter(prefix="/conversations")


@router.get("/", response_model=list[ConversationListResponse])
async def list_conversations(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """List all conversations for the current user."""
    try:
        conversations = await conversation_repository.list_for_user(db, current_user.id)
        return [
            ConversationListResponse(**conv.to_dict(include_messages=False))
            for conv in conversations
        ]
    except Exception as e:
        logger.error("list_conversations_error", error=str(e), user_id=current_user.id)
        raise HTTPException(status_code=500, detail="Failed to list conversations")


@router.post("/", response_model=ConversationResponse)
async def create_conversation(
    request: CreateConversationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Create a new conversation."""
    try:
        conversation = await conversation_repository.create(
            db, title=request.title, conv_type=request.type.value, user_id=current_user.id
        )
        conv_dict = conversation.to_dict(include_messages=False)
        conv_dict["messages"] = []
        return ConversationResponse(**conv_dict)
    except Exception as e:
        await db.rollback()
        logger.error("create_conversation_error", error=str(e), user_id=current_user.id)
        raise HTTPException(status_code=500, detail="Failed to create conversation")


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Get a specific conversation with all messages."""
    try:
        conversation = await conversation_repository.get_with_messages(
            db, conversation_id, current_user.id
        )
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return ConversationResponse(**conversation.to_dict(include_messages=True))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "get_conversation_error",
            error=str(e),
            conversation_id=conversation_id,
            user_id=current_user.id,
        )
        raise HTTPException(status_code=500, detail="Failed to get conversation")


@router.patch("/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
    conversation_id: str,
    request: UpdateConversationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Update a conversation."""
    try:
        if request.title is not None:
            updated = await conversation_repository.update_title(
                db, conversation_id, current_user.id, request.title
            )
            if not updated:
                raise HTTPException(status_code=404, detail="Conversation not found")
            return ConversationResponse(**updated.to_dict(include_messages=True))
        else:
            conversation = await conversation_repository.get_with_messages(
                db, conversation_id, current_user.id
            )
            if not conversation:
                raise HTTPException(status_code=404, detail="Conversation not found")
            return ConversationResponse(**conversation.to_dict(include_messages=True))
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(
            "update_conversation_error",
            error=str(e),
            conversation_id=conversation_id,
            user_id=current_user.id,
        )
        raise HTTPException(status_code=500, detail="Failed to update conversation")


@router.post("/{conversation_id}/generate-title", response_model=ConversationResponse)
async def generate_conversation_title(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Generate a meaningful title for the conversation using LLM."""
    try:
        conversation = await conversation_repository.get_with_messages(
            db, conversation_id, current_user.id
        )
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        first_user_message = next(
            (m for m in conversation.messages if m.role == "user"), None
        )
        if not first_user_message:
            return ConversationResponse(**conversation.to_dict(include_messages=True))

        from app.ai.llm import llm_service

        new_title = await llm_service.generate_title(first_user_message.content)
        if new_title:
            updated = await conversation_repository.update_title(
                db, conversation_id, current_user.id, new_title
            )
            if updated:
                return ConversationResponse(**updated.to_dict(include_messages=True))

        return ConversationResponse(**conversation.to_dict(include_messages=True))
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(
            "generate_conversation_title_error",
            error=str(e),
            conversation_id=conversation_id,
            user_id=current_user.id,
        )
        raise HTTPException(status_code=500, detail="Failed to generate title")


@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Delete a conversation."""
    try:
        deleted = await conversation_repository.delete(db, conversation_id, current_user.id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return {"status": "deleted", "conversation_id": conversation_id}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(
            "delete_conversation_error",
            error=str(e),
            conversation_id=conversation_id,
            user_id=current_user.id,
        )
        raise HTTPException(status_code=500, detail="Failed to delete conversation")


@router.post("/{conversation_id}/messages", response_model=ConversationMessageResponse)
async def create_message(
    conversation_id: str,
    request: CreateMessageRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Add a message to a conversation."""
    try:
        message = await conversation_repository.create_message(
            db,
            conversation_id=conversation_id,
            user_id=current_user.id,
            role=request.role.value,
            content=request.content,
            metadata=request.metadata,
            attachment_ids=request.attachment_ids,
        )
        if not message:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return ConversationMessageResponse(**message.to_dict())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(
            "create_message_error",
            error=str(e),
            conversation_id=conversation_id,
            user_id=current_user.id,
        )
        raise HTTPException(status_code=500, detail="Failed to create message")


@router.patch("/{conversation_id}/messages/{message_id}", response_model=ConversationMessageResponse)
async def update_message(
    conversation_id: str,
    message_id: str,
    request: UpdateMessageRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Update a message in a conversation."""
    try:
        message = await conversation_repository.update_message(
            db, conversation_id, message_id, current_user.id, request.content
        )
        if not message:
            raise HTTPException(status_code=404, detail="Conversation or message not found")
        return ConversationMessageResponse(**message.to_dict())
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(
            "update_message_error",
            error=str(e),
            conversation_id=conversation_id,
            message_id=message_id,
            user_id=current_user.id,
        )
        raise HTTPException(status_code=500, detail="Failed to update message")


@router.delete("/{conversation_id}/messages/{message_id}")
async def delete_message(
    conversation_id: str,
    message_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Delete a message from a conversation."""
    try:
        deleted = await conversation_repository.delete_message(
            db, conversation_id, message_id, current_user.id
        )
        if not deleted:
            raise HTTPException(status_code=404, detail="Conversation or message not found")
        return {"status": "deleted", "message_id": message_id}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(
            "delete_message_error",
            error=str(e),
            conversation_id=conversation_id,
            message_id=message_id,
            user_id=current_user.id,
        )
        raise HTTPException(status_code=500, detail="Failed to delete message")
