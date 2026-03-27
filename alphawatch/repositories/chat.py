"""Chat session repository — session CRUD, turn persistence, and rolling summary."""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from alphawatch.models.chat import ChatSession


class ChatRepository:
    """Data access for chat sessions.

    Manages session lifecycle, message appending, chunk cache updates,
    and rolling context summary for long conversations.

    Args:
        session: An async SQLAlchemy session.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_session(
        self,
        user_id: uuid.UUID,
        company_id: uuid.UUID,
        ticker: str,
    ) -> ChatSession:
        """Create a new chat session for a user + company pair.

        Args:
            user_id: UUID of the requesting user.
            company_id: UUID of the company being discussed.
            ticker: Active company ticker for display context.

        Returns:
            The newly created ChatSession (not yet committed).
        """
        chat_session = ChatSession(
            user_id=user_id,
            company_id=company_id,
            active_company_ticker=ticker,
            messages=[],
            retrieved_chunk_ids=[],
            context_summary=None,
            context_summary_through=0,
        )
        self._session.add(chat_session)
        await self._session.flush()
        return chat_session

    async def get_session(
        self,
        session_id: uuid.UUID,
    ) -> ChatSession | None:
        """Fetch a chat session by primary key.

        Args:
            session_id: UUID of the ChatSession.

        Returns:
            The ChatSession if found, otherwise None.
        """
        return await self._session.get(ChatSession, session_id)

    async def get_sessions_for_user_company(
        self,
        user_id: uuid.UUID,
        company_id: uuid.UUID,
        limit: int = 10,
    ) -> list[ChatSession]:
        """List recent chat sessions for a user + company pair.

        Args:
            user_id: UUID of the requesting user.
            company_id: UUID of the company.
            limit: Maximum number of sessions to return.

        Returns:
            List of ChatSession objects ordered by updated_at desc.
        """
        stmt = (
            select(ChatSession)
            .where(
                ChatSession.user_id == user_id,
                ChatSession.company_id == company_id,
            )
            .order_by(ChatSession.updated_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def append_messages(
        self,
        session_id: uuid.UUID,
        user_message: dict[str, Any],
        assistant_message: dict[str, Any],
    ) -> ChatSession:
        """Append a user+assistant turn to the session message list.

        Each message dict should contain at minimum 'role', 'content',
        and 'created_at'. Assistant messages may include 'citations'.

        Args:
            session_id: UUID of the target ChatSession.
            user_message: Dict representation of the user turn.
            assistant_message: Dict representation of the assistant turn.

        Returns:
            The updated ChatSession.

        Raises:
            ValueError: If the session does not exist.
        """
        chat_session = await self._session.get(ChatSession, session_id)
        if chat_session is None:
            raise ValueError(f"ChatSession {session_id} not found")

        # PostgreSQL ARRAY(JSONB) requires reassignment (not in-place mutation)
        # to trigger SQLAlchemy dirty-tracking.
        current = list(chat_session.messages or [])
        current.append(user_message)
        current.append(assistant_message)
        chat_session.messages = current

        await self._session.flush()
        return chat_session

    async def update_chunk_cache(
        self,
        session_id: uuid.UUID,
        chunk_ids: list[str],
    ) -> ChatSession:
        """Merge new chunk IDs into the session's chunk cache.

        Deduplicates against already-cached IDs so the array stays
        compact. Preserves insertion order of new IDs.

        Args:
            session_id: UUID of the target ChatSession.
            chunk_ids: Chunk UUID strings retrieved during this turn.

        Returns:
            The updated ChatSession.

        Raises:
            ValueError: If the session does not exist.
        """
        chat_session = await self._session.get(ChatSession, session_id)
        if chat_session is None:
            raise ValueError(f"ChatSession {session_id} not found")

        existing = {str(cid) for cid in (chat_session.retrieved_chunk_ids or [])}
        new_ids = [cid for cid in chunk_ids if cid not in existing]

        if new_ids:
            updated = list(chat_session.retrieved_chunk_ids or []) + [
                uuid.UUID(cid) for cid in new_ids
            ]
            chat_session.retrieved_chunk_ids = updated
            await self._session.flush()

        return chat_session

    async def update_context_summary(
        self,
        session_id: uuid.UUID,
        summary: str,
        summary_through: int,
    ) -> ChatSession:
        """Store a new rolling context summary for a long conversation.

        Called by the ``maybe_summarize`` node when the session message
        count exceeds the threshold (20 messages). Tracks which message
        index the summary covers so the graph knows what to include in
        the raw-message window.

        Args:
            session_id: UUID of the target ChatSession.
            summary: The new rolling summary text (~300 tokens).
            summary_through: Index of the last message captured by this summary.

        Returns:
            The updated ChatSession.

        Raises:
            ValueError: If the session does not exist.
        """
        chat_session = await self._session.get(ChatSession, session_id)
        if chat_session is None:
            raise ValueError(f"ChatSession {session_id} not found")

        chat_session.context_summary = summary
        chat_session.context_summary_through = summary_through
        await self._session.flush()
        return chat_session

    async def get_messages(
        self,
        session_id: uuid.UUID,
    ) -> list[dict[str, Any]]:
        """Return all stored messages for a session.

        Args:
            session_id: UUID of the ChatSession.

        Returns:
            List of message dicts in chronological order, or an empty
            list if the session does not exist.
        """
        chat_session = await self._session.get(ChatSession, session_id)
        if chat_session is None:
            return []
        return list(chat_session.messages or [])

    async def delete_session(
        self,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> bool:
        """Delete a chat session, enforcing ownership.

        Args:
            session_id: UUID of the ChatSession to delete.
            user_id: UUID of the requesting user (ownership check).

        Returns:
            True if the session was found and deleted, False otherwise.
        """
        chat_session = await self._session.get(ChatSession, session_id)
        if chat_session is None or chat_session.user_id != user_id:
            return False

        await self._session.delete(chat_session)
        await self._session.flush()
        return True
