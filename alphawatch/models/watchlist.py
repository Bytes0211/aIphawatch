"""Watchlist ORM model."""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Index, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from alphawatch.database import Base


class WatchlistEntry(Base):
    """User's watchlist entry linking a user to a company.

    Attributes:
        id: Primary key UUID.
        user_id: FK to users.
        company_id: FK to companies.
        alert_thresholds: JSONB alert configuration.
        created_at: Record creation timestamp.
    """

    __tablename__ = "watchlist"
    __table_args__ = (
        UniqueConstraint("user_id", "company_id", name="uq_watchlist_user_company"),
        Index("idx_watchlist_user", "user_id"),
        Index("idx_watchlist_company", "company_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False
    )
    alert_thresholds: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(server_default=text("NOW()"))

    user: Mapped["User"] = relationship()  # noqa: F821
    company: Mapped["Company"] = relationship()  # noqa: F821
