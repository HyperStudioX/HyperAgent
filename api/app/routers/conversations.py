"""Router for conversation management."""

import uuid
from typing import Sequence

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import CurrentUser, get_current_user
from app.core.logging import get_logger
from app.db.base import get_db
from app.db.models import Conversation, ConversationMessage
from app.models.schemas import (
    ConversationListResponse,
    ConversationMessageResponse,
    ConversationResponse,
    CreateConversationRequest,
    CreateMessageRequest,
    UpdateConversationRequest,
    UpdateMessageRequest,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/conversations")


@router.get("/", response_model=list[ConversationListResponse])
async def list_conversations(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """List all conversations for the current user."""
    try:
        result = await db.execute(
            select(Conversation)
            .where(Conversation.user_id == current_user.id)
            .order_by(Conversation.updated_at.desc())
        )
        conversations: Sequence[Conversation] = result.scalars().all()

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
        conversation = Conversation(
            id=str(uuid.uuid4()),
            title=request.title,
            type=request.type.value,
            user_id=current_user.id,
        )
        db.add(conversation)
        await db.commit()
        await db.refresh(conversation)

        return ConversationResponse(**conversation.to_dict(include_messages=True))
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
        result = await db.execute(
            select(Conversation)
            .options(selectinload(Conversation.messages))
            .where(
                Conversation.id == conversation_id,
                Conversation.user_id == current_user.id,
            )
        )
        conversation = result.scalar_one_or_none()

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
        result = await db.execute(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.user_id == current_user.id,
            )
        )
        conversation = result.scalar_one_or_none()

        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        if request.title is not None:
            conversation.title = request.title

        await db.commit()
        await db.refresh(conversation)

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


@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Delete a conversation."""
    try:
        result = await db.execute(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.user_id == current_user.id,
            )
        )
        conversation = result.scalar_one_or_none()

        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        await db.delete(conversation)
        await db.commit()

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
        # Verify conversation exists and belongs to user
        result = await db.execute(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.user_id == current_user.id,
            )
        )
        conversation = result.scalar_one_or_none()

        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        # Create message
        message = ConversationMessage(
            id=str(uuid.uuid4()),
            conversation_id=conversation_id,
            role=request.role.value,
            content=request.content,
            message_metadata=request.metadata,
        )
        db.add(message)
        await db.commit()
        await db.refresh(message)

        return ConversationMessageResponse(**message.to_dict())
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
        # Verify conversation belongs to user
        result = await db.execute(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.user_id == current_user.id,
            )
        )
        conversation = result.scalar_one_or_none()

        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        # Get and update message
        result = await db.execute(
            select(ConversationMessage).where(
                ConversationMessage.id == message_id,
                ConversationMessage.conversation_id == conversation_id,
            )
        )
        message = result.scalar_one_or_none()

        if not message:
            raise HTTPException(status_code=404, detail="Message not found")

        message.content = request.content
        await db.commit()
        await db.refresh(message)

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
        # Verify conversation belongs to user
        result = await db.execute(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.user_id == current_user.id,
            )
        )
        conversation = result.scalar_one_or_none()

        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        # Get and delete message
        result = await db.execute(
            select(ConversationMessage).where(
                ConversationMessage.id == message_id,
                ConversationMessage.conversation_id == conversation_id,
            )
        )
        message = result.scalar_one_or_none()

        if not message:
            raise HTTPException(status_code=404, detail="Message not found")

        await db.delete(message)
        await db.commit()

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
