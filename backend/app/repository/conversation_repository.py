"""Conversation repository for conversation and message persistence."""

import uuid
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import get_logger
from app.db.models import (
    Conversation,
    ConversationMessage,
    File,
    MessageAttachment,
)

logger = get_logger(__name__)


class ConversationRepository:
    """Repository for persisting conversations and messages."""

    async def list_for_user(
        self, db: AsyncSession, user_id: str
    ) -> Sequence[Conversation]:
        """List all conversations for a user, ordered by most recent."""
        result = await db.execute(
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.updated_at.desc())
        )
        return result.scalars().all()

    async def create(
        self, db: AsyncSession, title: str, conv_type: str, user_id: str
    ) -> Conversation:
        """Create a new conversation."""
        conversation = Conversation(
            id=str(uuid.uuid4()),
            title=title,
            type=conv_type,
            user_id=user_id,
        )
        db.add(conversation)
        await db.commit()
        await db.refresh(conversation)
        return conversation

    async def get_with_messages(
        self, db: AsyncSession, conversation_id: str, user_id: str
    ) -> Conversation | None:
        """Get a conversation with all messages and attachments."""
        result = await db.execute(
            select(Conversation)
            .options(
                selectinload(Conversation.messages)
                .selectinload(ConversationMessage.attachments)
                .selectinload(MessageAttachment.file)
            )
            .where(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_for_user(
        self, db: AsyncSession, conversation_id: str, user_id: str
    ) -> Conversation | None:
        """Get a conversation (without messages) verifying ownership."""
        result = await db.execute(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def update_title(
        self, db: AsyncSession, conversation_id: str, user_id: str, title: str
    ) -> Conversation | None:
        """Update conversation title. Returns updated conversation or None."""
        conversation = await self.get_with_messages(db, conversation_id, user_id)
        if not conversation:
            return None
        conversation.title = title
        await db.commit()
        # Re-query to get fresh data
        return await self.get_with_messages(db, conversation_id, user_id)

    async def delete(
        self, db: AsyncSession, conversation_id: str, user_id: str
    ) -> bool:
        """Delete a conversation. Returns True if deleted, False if not found."""
        conversation = await self.get_for_user(db, conversation_id, user_id)
        if not conversation:
            return False
        await db.delete(conversation)
        await db.commit()
        return True

    async def get_recent_history(
        self,
        db: AsyncSession,
        conversation_id: str,
        user_id: str,
        limit: int = 20,
    ) -> list[dict]:
        """Fetch recent conversation history for short-term memory."""
        # Verify ownership
        conv = await self.get_for_user(db, conversation_id, user_id)
        if not conv:
            return []

        message_result = await db.execute(
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id == conversation_id)
            .order_by(ConversationMessage.created_at.desc())
            .limit(limit)
        )
        messages = list(reversed(message_result.scalars().all()))
        return [
            {
                "role": message.role,
                "content": message.content,
                "metadata": message.message_metadata,
            }
            for message in messages
            if message.role in ("user", "assistant")
        ]

    async def create_message(
        self,
        db: AsyncSession,
        conversation_id: str,
        user_id: str,
        role: str,
        content: str,
        metadata: dict | None = None,
        attachment_ids: list[str] | None = None,
    ) -> ConversationMessage | None:
        """Create a message in a conversation. Returns None if conversation not found."""
        conversation = await self.get_for_user(db, conversation_id, user_id)
        if not conversation:
            return None

        message = ConversationMessage(
            id=str(uuid.uuid4()),
            conversation_id=conversation_id,
            role=role,
            content=content,
            message_metadata=metadata,
        )
        db.add(message)
        await db.flush()

        # Handle attachments
        if attachment_ids:
            result = await db.execute(
                select(File).where(
                    File.id.in_(attachment_ids),
                    File.user_id == user_id,
                )
            )
            files = result.scalars().all()
            found_file_ids = {f.id for f in files}
            invalid_ids = set(attachment_ids) - found_file_ids
            if invalid_ids:
                raise ValueError(f"Invalid attachment IDs: {', '.join(invalid_ids)}")

            for file in files:
                attachment = MessageAttachment(
                    id=str(uuid.uuid4()),
                    message_id=message.id,
                    file_id=file.id,
                )
                db.add(attachment)

        await db.commit()

        # Reload with attachments
        result = await db.execute(
            select(ConversationMessage)
            .options(
                selectinload(ConversationMessage.attachments).selectinload(
                    MessageAttachment.file
                )
            )
            .where(ConversationMessage.id == message.id)
        )
        return result.scalar_one()

    async def update_message(
        self,
        db: AsyncSession,
        conversation_id: str,
        message_id: str,
        user_id: str,
        content: str,
    ) -> ConversationMessage | None:
        """Update a message. Returns None if not found."""
        conversation = await self.get_for_user(db, conversation_id, user_id)
        if not conversation:
            return None

        result = await db.execute(
            select(ConversationMessage).where(
                ConversationMessage.id == message_id,
                ConversationMessage.conversation_id == conversation_id,
            )
        )
        message = result.scalar_one_or_none()
        if not message:
            return None

        message.content = content
        await db.commit()
        await db.refresh(message)
        return message

    async def delete_message(
        self,
        db: AsyncSession,
        conversation_id: str,
        message_id: str,
        user_id: str,
    ) -> bool:
        """Delete a message. Returns True if deleted, False if not found."""
        conversation = await self.get_for_user(db, conversation_id, user_id)
        if not conversation:
            return False

        result = await db.execute(
            select(ConversationMessage).where(
                ConversationMessage.id == message_id,
                ConversationMessage.conversation_id == conversation_id,
            )
        )
        message = result.scalar_one_or_none()
        if not message:
            return False

        await db.delete(message)
        await db.commit()
        return True


# Module-level singleton
conversation_repository = ConversationRepository()
