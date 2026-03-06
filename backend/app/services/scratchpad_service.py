"""Scratchpad storage service for context offloading."""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from dataclasses import dataclass

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

SCRATCHPAD_MEMORY_TYPE = "procedural"
SCRATCHPAD_NAMESPACE = "scratchpad"
SCRATCHPAD_MAX_READ_CHARS = 4000


@dataclass
class ScratchpadPayload:
    """Scratchpad read payload."""

    notes: str
    scope: str
    namespace: str
    updated_at: float


class ScratchpadService:
    """Stores short-term and persistent scratchpad notes."""

    def __init__(self) -> None:
        # Session-scope notes: (user_id, task_id, namespace) -> payload
        self._session_notes: dict[tuple[str, str, str], ScratchpadPayload] = {}
        self._persistent_fallback: dict[tuple[str, str], ScratchpadPayload] = {}
        self._lock = asyncio.Lock()

    def _effective_namespace(self, namespace: str | None, task_id: str | None) -> str:
        if namespace and namespace.strip():
            return namespace.strip()
        if task_id:
            return f"task:{task_id}"
        return "default"

    def _clip_notes(self, notes: str, max_chars: int = SCRATCHPAD_MAX_READ_CHARS) -> str:
        if len(notes) <= max_chars:
            return notes
        clipped = notes[:max_chars]
        return f"{clipped}\n...[truncated]"

    async def write(
        self,
        *,
        notes: str,
        user_id: str | None,
        task_id: str | None,
        scope: str,
        namespace: str | None = None,
    ) -> ScratchpadPayload:
        """Write notes to session or persistent scratchpad storage."""
        normalized_scope = "persistent" if scope == "persistent" else "session"
        effective_namespace = self._effective_namespace(namespace, task_id)
        entry = ScratchpadPayload(
            notes=self._clip_notes(notes, max_chars=12000),
            scope=normalized_scope,
            namespace=effective_namespace,
            updated_at=time.time(),
        )

        if normalized_scope == "session":
            if not user_id:
                return entry
            async with self._lock:
                self._session_notes[(user_id, task_id or "", effective_namespace)] = entry
            return entry

        # persistent scope
        if not settings.context_offloading_persistent_enabled or not user_id:
            async with self._lock:
                self._persistent_fallback[(user_id or "anonymous", effective_namespace)] = entry
            return entry

        try:
            from app.db.base import async_session_maker
            from app.db.models import Memory
            from sqlalchemy import select

            async with async_session_maker() as session:
                stmt = (
                    select(Memory)
                    .where(Memory.user_id == user_id)
                    .where(Memory.memory_type == SCRATCHPAD_MEMORY_TYPE)
                )
                result = await session.execute(stmt)
                candidates = result.scalars().all()

                target = None
                for row in candidates:
                    meta = {}
                    if row.metadata_json:
                        try:
                            meta = json.loads(row.metadata_json)
                        except (json.JSONDecodeError, TypeError):
                            meta = {}
                    if (
                        meta.get("namespace") == SCRATCHPAD_NAMESPACE
                        and meta.get("scratchpad_scope") == "persistent"
                        and meta.get("key") == effective_namespace
                    ):
                        target = row
                        break

                metadata = {
                    "namespace": SCRATCHPAD_NAMESPACE,
                    "scratchpad_scope": "persistent",
                    "key": effective_namespace,
                    "task_id": task_id,
                }
                if target is None:
                    target = Memory(
                        id=str(uuid.uuid4()),
                        user_id=user_id,
                        memory_type=SCRATCHPAD_MEMORY_TYPE,
                        content=entry.notes,
                        metadata_json=json.dumps(metadata),
                        source_conversation_id=task_id,
                    )
                    session.add(target)
                else:
                    target.content = entry.notes
                    target.metadata_json = json.dumps(metadata)
                    target.source_conversation_id = task_id

                await session.commit()
            return entry
        except Exception as e:
            logger.warning("scratchpad_persistent_write_fallback", error=str(e))
            async with self._lock:
                self._persistent_fallback[(user_id, effective_namespace)] = entry
            return entry

    async def read(
        self,
        *,
        user_id: str | None,
        task_id: str | None,
        scope: str,
        namespace: str | None = None,
    ) -> ScratchpadPayload | None:
        """Read notes from session or persistent scratchpad storage."""
        normalized_scope = "persistent" if scope == "persistent" else "session"
        effective_namespace = self._effective_namespace(namespace, task_id)

        if normalized_scope == "session":
            if not user_id:
                return None
            async with self._lock:
                return self._session_notes.get((user_id, task_id or "", effective_namespace))

        if not user_id:
            return None

        if settings.context_offloading_persistent_enabled:
            try:
                from app.db.base import async_session_maker
                from app.db.models import Memory
                from sqlalchemy import select

                async with async_session_maker() as session:
                    stmt = (
                        select(Memory)
                        .where(Memory.user_id == user_id)
                        .where(Memory.memory_type == SCRATCHPAD_MEMORY_TYPE)
                    )
                    result = await session.execute(stmt)
                    for row in result.scalars().all():
                        meta = {}
                        if row.metadata_json:
                            try:
                                meta = json.loads(row.metadata_json)
                            except (json.JSONDecodeError, TypeError):
                                meta = {}
                        if (
                            meta.get("namespace") == SCRATCHPAD_NAMESPACE
                            and meta.get("scratchpad_scope") == "persistent"
                            and meta.get("key") == effective_namespace
                        ):
                            return ScratchpadPayload(
                                notes=self._clip_notes(row.content),
                                scope="persistent",
                                namespace=effective_namespace,
                                updated_at=time.time(),
                            )
            except Exception as e:
                logger.warning("scratchpad_persistent_read_fallback", error=str(e))

        async with self._lock:
            return self._persistent_fallback.get((user_id, effective_namespace))

    async def get_compact_context(
        self,
        *,
        user_id: str | None,
        task_id: str | None,
        max_chars: int = 1200,
    ) -> str | None:
        """Build a compact scratchpad context snippet for prompt injection."""
        if not settings.context_offloading_enabled or not user_id:
            return None

        snippets: list[str] = []
        session_entry = await self.read(
            user_id=user_id,
            task_id=task_id,
            scope="session",
            namespace=None,
        )
        if session_entry and session_entry.notes:
            snippets.append(f"Session scratchpad:\n{session_entry.notes}")

        if settings.context_offloading_persistent_enabled:
            persistent_entry = await self.read(
                user_id=user_id,
                task_id=task_id,
                scope="persistent",
                namespace=None,
            )
            if persistent_entry and persistent_entry.notes:
                snippets.append(f"Persistent scratchpad:\n{persistent_entry.notes}")

        if not snippets:
            return None

        combined = "\n\n".join(snippets)
        if len(combined) > max_chars:
            combined = combined[:max_chars] + "\n...[scratchpad context truncated]"
        return f"[Scratchpad Context]\n{combined}"


_scratchpad_service = ScratchpadService()


def get_scratchpad_service() -> ScratchpadService:
    """Get singleton scratchpad service."""
    return _scratchpad_service

