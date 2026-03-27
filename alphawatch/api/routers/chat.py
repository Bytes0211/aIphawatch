"""Chat session API endpoints with SSE streaming."""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from alphawatch.api.dependencies import get_current_user, get_db
from alphawatch.repositories.chat import ChatRepository
from alphawatch.repositories.companies import CompanyRepository
from alphawatch.schemas.auth import CurrentUser
from alphawatch.schemas.chat import (
    ChatSessionCreateRequest,
    ChatSessionListResponse,
    ChatSessionResponse,
    MessageHistoryResponse,
    MessageSchema,
    SendMessageRequest,
    SSECitationsEvent,
    SSEDoneEvent,
    SSEErrorEvent,
    SSEFollowupsEvent,
    SSETokenEvent,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])


# ---------------------------------------------------------------------------
# Session CRUD
# ---------------------------------------------------------------------------


@router.post("/sessions", response_model=ChatSessionResponse, status_code=201)
async def create_session(
    body: ChatSessionCreateRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatSessionResponse:
    """Create a new chat session for a company.

    Args:
        body: Request body with company_id and ticker.
        user: The authenticated user (injected).
        db: Database session (injected).

    Returns:
        The newly created ChatSession.

    Raises:
        HTTPException: 404 if the company does not exist.
    """
    company_repo = CompanyRepository(db)
    company = await company_repo.get_by_id(body.company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    chat_repo = ChatRepository(db)
    session = await chat_repo.create_session(
        user_id=uuid.UUID(user.user_id),
        company_id=body.company_id,
        ticker=body.ticker.upper(),
    )
    return ChatSessionResponse.model_validate(session)


@router.get("/sessions", response_model=ChatSessionListResponse)
async def list_sessions(
    company_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatSessionListResponse:
    """List recent chat sessions for a user + company pair.

    Args:
        company_id: Filter sessions by company UUID (query parameter).
        user: The authenticated user (injected).
        db: Database session (injected).

    Returns:
        List of chat session summaries ordered by most-recently-updated.
    """
    chat_repo = ChatRepository(db)
    sessions = await chat_repo.get_sessions_for_user_company(
        user_id=uuid.UUID(user.user_id),
        company_id=company_id,
    )
    return ChatSessionListResponse(
        sessions=[ChatSessionResponse.model_validate(s) for s in sessions],
        count=len(sessions),
    )


@router.get("/sessions/{session_id}", response_model=ChatSessionResponse)
async def get_session(
    session_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatSessionResponse:
    """Fetch a single chat session by ID.

    Args:
        session_id: UUID of the ChatSession to retrieve.
        user: The authenticated user (injected).
        db: Database session (injected).

    Returns:
        The ChatSession if found and owned by the user.

    Raises:
        HTTPException: 404 if not found or not owned by user.
    """
    chat_repo = ChatRepository(db)
    session = await chat_repo.get_session(session_id)

    if session is None or session.user_id != uuid.UUID(user.user_id):
        raise HTTPException(status_code=404, detail="Session not found")

    return ChatSessionResponse.model_validate(session)


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(
    session_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a chat session (ownership-enforced).

    Args:
        session_id: UUID of the ChatSession to delete.
        user: The authenticated user (injected).
        db: Database session (injected).

    Raises:
        HTTPException: 404 if not found or not owned by the requesting user.
    """
    chat_repo = ChatRepository(db)
    deleted = await chat_repo.delete_session(
        session_id=session_id,
        user_id=uuid.UUID(user.user_id),
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")


# ---------------------------------------------------------------------------
# Message history
# ---------------------------------------------------------------------------


@router.get(
    "/sessions/{session_id}/messages",
    response_model=MessageHistoryResponse,
)
async def get_messages(
    session_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageHistoryResponse:
    """Return the full message history for a chat session.

    Args:
        session_id: UUID of the ChatSession.
        user: The authenticated user (injected).
        db: Database session (injected).

    Returns:
        All messages in chronological order.

    Raises:
        HTTPException: 404 if session not found or not owned by user.
    """
    chat_repo = ChatRepository(db)
    session = await chat_repo.get_session(session_id)

    if session is None or session.user_id != uuid.UUID(user.user_id):
        raise HTTPException(status_code=404, detail="Session not found")

    raw_messages: list[dict[str, Any]] = await chat_repo.get_messages(session_id)
    messages = [
        MessageSchema(
            role=m.get("role", "user"),
            content=m.get("content", ""),
            citations=m.get("citations", []),
            suggested_followups=m.get("suggested_followups", []),
            turn_index=m.get("turn_index", i),
            created_at=m.get("created_at", ""),
        )
        for i, m in enumerate(raw_messages)
    ]
    return MessageHistoryResponse(
        session_id=session_id,
        messages=messages,
        count=len(messages),
    )


# ---------------------------------------------------------------------------
# SSE streaming message endpoint
# ---------------------------------------------------------------------------


@router.post("/sessions/{session_id}/messages")
async def send_message(
    session_id: uuid.UUID,
    body: SendMessageRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Send a user message and stream the assistant response via SSE.

    Runs the ChatGraph and emits a sequence of Server-Sent Events:

    1. ``token`` events — one per sentence fragment of the response
       (simulated from the complete Bedrock response, which is not
       natively streaming in this implementation).
    2. ``citations`` event — source citations for the response.
    3. ``followups`` event — suggested follow-up question chips.
    4. ``done`` event — signals the end of the stream.

    On error, emits a single ``error`` event before closing the stream.

    Args:
        session_id: UUID of the ChatSession to send the message to.
        body: Request body containing the user's message text.
        user: The authenticated user (injected).
        db: Database session (injected).

    Returns:
        A ``StreamingResponse`` with ``text/event-stream`` content type.

    Raises:
        HTTPException: 404 if session not found or not owned by user,
            422 if message is empty.
    """
    # Validate ownership before streaming begins
    chat_repo = ChatRepository(db)
    session = await chat_repo.get_session(session_id)
    if session is None or session.user_id != uuid.UUID(user.user_id):
        raise HTTPException(status_code=404, detail="Session not found")

    if not body.message.strip():
        raise HTTPException(status_code=422, detail="Message cannot be empty")

    # Fetch company context for the graph
    company_repo = CompanyRepository(db)
    company = await company_repo.get_by_id(session.company_id)
    company_name = company.name if company else session.active_company_ticker

    async def event_generator() -> AsyncGenerator[str, None]:
        """Inner generator that runs the ChatGraph and yields SSE lines.

        Yields:
            Newline-terminated ``data: <json>`` strings conforming to
            the SSE wire format.
        """

        def _sse(payload: dict[str, Any]) -> str:
            return f"data: {json.dumps(payload)}\n\n"

        try:
            # Import here to avoid heavy graph init at module load
            from alphawatch.agents.graphs.chat import build_chat_graph

            graph = build_chat_graph()

            initial_state: dict[str, Any] = {
                "tenant_id": user.tenant_id,
                "user_id": user.user_id,
                "company_id": str(session.company_id),
                "ticker": session.active_company_ticker,
                "company_name": company_name,
                "session_id": str(session_id),
                "user_message": body.message.strip(),
                "errors": [],
                "metadata": {},
            }

            result = await graph.ainvoke(initial_state)

            response_text: str = result.get("response", "")
            citations: list[dict[str, Any]] = [
                {
                    "chunk_id": c.chunk_id,
                    "document_id": c.document_id,
                    "title": c.title,
                    "source_type": c.source_type,
                    "source_url": c.source_url,
                    "excerpt": c.excerpt,
                }
                for c in result.get("citations", [])
            ]
            followups: list[str] = result.get("suggested_followups", [])
            errors: list[str] = result.get("errors", [])

            if not response_text and errors:
                yield _sse(SSEErrorEvent(message=errors[0]).model_dump())
                return

            # Emit the response token-by-token (sentence-level granularity).
            # Bedrock's invoke() returns the complete text; we simulate
            # streaming by splitting on sentence boundaries so the UI can
            # show progressive rendering without native token streaming.
            import re

            sentences = re.split(r"(?<=[.!?])\s+", response_text.strip())
            if not sentences:
                sentences = [response_text]

            for sentence in sentences:
                if sentence:
                    yield _sse(SSETokenEvent(token=sentence + " ").model_dump())

            # Citations
            yield _sse(SSECitationsEvent(citations=citations).model_dump())

            # Follow-ups
            if followups:
                yield _sse(SSEFollowupsEvent(questions=followups).model_dump())

            # Done
            yield _sse(SSEDoneEvent(session_id=str(session_id)).model_dump())

        except Exception as exc:
            logger.exception("ChatGraph error for session %s: %s", session_id, exc)
            yield _sse(
                SSEErrorEvent(
                    message="An unexpected error occurred. Please try again."
                ).model_dump()
            )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable Nginx buffering for SSE
        },
    )
