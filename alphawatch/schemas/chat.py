"""Chat request/response Pydantic schemas."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

# ---------------------------------------------------------------------------
# Citation
# ---------------------------------------------------------------------------


class CitationSchema(BaseModel):
    """A source citation attached to an assistant message.

    Attributes:
        chunk_id: UUID string of the DocumentChunk cited.
        document_id: UUID string of the parent Document.
        title: Document title (e.g. 'Apple 10-K 2025').
        source_type: Filing type (edgar_10k, edgar_10q, etc.).
        source_url: Original filing URL.
        excerpt: Short text excerpt from the chunk.
    """

    chunk_id: str
    document_id: str
    title: str
    source_type: str
    source_url: str
    excerpt: str = ""


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------


class MessageSchema(BaseModel):
    """A single message in a chat session.

    Attributes:
        role: One of 'user', 'assistant', or 'system'.
        content: Message text content.
        citations: Source citations (assistant messages only).
        suggested_followups: Follow-up chips (final assistant message only).
        turn_index: Zero-based position in the session message list.
        created_at: ISO 8601 timestamp string.
    """

    model_config = ConfigDict(from_attributes=True)

    role: Literal["user", "assistant", "system"]
    content: str
    citations: list[CitationSchema] = []
    suggested_followups: list[str] = []
    turn_index: int = 0
    created_at: str = ""


# ---------------------------------------------------------------------------
# Session schemas
# ---------------------------------------------------------------------------


class ChatSessionCreateRequest(BaseModel):
    """Request body for creating a new chat session.

    Attributes:
        company_id: UUID of the company to discuss.
        ticker: Active company ticker for display context.
    """

    company_id: uuid.UUID
    ticker: str


class ChatSessionResponse(BaseModel):
    """Response after creating or fetching a chat session.

    Attributes:
        id: Chat session UUID.
        company_id: UUID of the associated company.
        user_id: UUID of the session owner.
        active_company_ticker: Active ticker for display context.
        created_at: Session creation timestamp.
        updated_at: Last modification timestamp.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    user_id: uuid.UUID
    active_company_ticker: str
    created_at: datetime
    updated_at: datetime


class ChatSessionListResponse(BaseModel):
    """Response for listing chat sessions.

    Attributes:
        sessions: List of session summaries.
        count: Total number of sessions returned.
    """

    sessions: list[ChatSessionResponse]
    count: int


# ---------------------------------------------------------------------------
# Message send / history
# ---------------------------------------------------------------------------


class SendMessageRequest(BaseModel):
    """Request body for sending a chat message.

    Attributes:
        message: The user's question or message text.
    """

    message: str


class MessageHistoryResponse(BaseModel):
    """Response for fetching the full message history of a session.

    Attributes:
        session_id: UUID of the chat session.
        messages: Ordered list of messages.
        count: Total number of messages.
    """

    session_id: uuid.UUID
    messages: list[MessageSchema]
    count: int


# ---------------------------------------------------------------------------
# SSE event schemas
# ---------------------------------------------------------------------------


class SSETokenEvent(BaseModel):
    """SSE event carrying a single response token (streaming).

    Attributes:
        type: Always 'token'.
        token: The text token fragment.
    """

    type: Literal["token"] = "token"
    token: str


class SSECitationsEvent(BaseModel):
    """SSE event carrying the full citation list after streaming ends.

    Attributes:
        type: Always 'citations'.
        citations: List of source citations for the response.
    """

    type: Literal["citations"] = "citations"
    citations: list[CitationSchema]


class SSEFollowupsEvent(BaseModel):
    """SSE event carrying suggested follow-up questions.

    Attributes:
        type: Always 'followups'.
        questions: List of follow-up question strings.
    """

    type: Literal["followups"] = "followups"
    questions: list[str]


class SSEDoneEvent(BaseModel):
    """SSE event signalling the end of the stream.

    Attributes:
        type: Always 'done'.
        session_id: UUID string of the session that was updated.
    """

    type: Literal["done"] = "done"
    session_id: str


class SSEErrorEvent(BaseModel):
    """SSE event carrying an error message.

    Attributes:
        type: Always 'error'.
        message: Human-readable error description.
    """

    type: Literal["error"] = "error"
    message: str
