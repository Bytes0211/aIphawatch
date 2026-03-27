"""Chat session ORM model."""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Index, Integer, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from alphawatch.database import Base


class ChatSession(Base):
    """Multi-turn RAG chat session for a company.

    Attributes:
        id: Primary key UUID.
        user_id: FK to users.
        company_id: FK to companies.
        active_company_ticker: Current ticker for display context.
        messages: Array of JSONB message objects.
        context_summary: Rolling summary of older messages.
        context_summary_through: Index of last summarized message.
        retrieved_chunk_ids: Cached chunk IDs for cache-hit optimization.
        created_at: Record creation timestamp.
        updated_at: Last modification timestamp.
    """

    __tablename__ = "chat_sessions"
    __table_args__ = (
        Index("idx_sessions_user_company", "user_id", "company_id", "updated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    active_company_ticker: Mapped[str] = mapped_column(Text, nullable=False)
    messages: Mapped[list] = mapped_column(
        ARRAY(JSONB), nullable=False, server_default="{}"
    )
    context_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    context_summary_through: Mapped[int] = mapped_column(
        Integer, server_default=text("0")
    )
    retrieved_chunk_ids: Mapped[list] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=False, server_default="{}"
    )
    created_at: Mapped[datetime] = mapped_column(server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("NOW()"), onupdate=text("NOW()"))
