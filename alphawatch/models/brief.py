"""Analyst brief and brief section ORM models."""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Index, Integer, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from alphawatch.database import Base


class AnalystBrief(Base):
    """Generated analyst brief for a company.

    Attributes:
        id: Primary key UUID.
        user_id: FK to users who requested the brief.
        company_id: FK to companies.
        session_id: UUID linking this brief to a generation session.
        generated_at: Timestamp of brief generation.
    """

    __tablename__ = "analyst_briefs"
    __table_args__ = (
        Index(
            "idx_briefs_user_company", "user_id", "company_id", "generated_at",
        ),
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
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(server_default=text("NOW()"))

    sections: Mapped[list["BriefSection"]] = relationship(back_populates="brief")


class BriefSection(Base):
    """Individual section within an analyst brief.

    Attributes:
        id: Primary key UUID.
        brief_id: FK to analyst_briefs.
        section_type: One of header, snapshot, what_changed, risk_flags,
            sentiment, executive_summary, sources, suggested_followups.
        section_order: Display ordering integer.
        content: JSONB section content (schema varies by type).
        created_at: Record creation timestamp.
    """

    __tablename__ = "brief_sections"
    __table_args__ = (
        UniqueConstraint("brief_id", "section_type", name="uq_brief_sections_type"),
        Index("idx_brief_sections_brief", "brief_id", "section_order"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    brief_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("analyst_briefs.id", ondelete="CASCADE"),
        nullable=False,
    )
    section_type: Mapped[str] = mapped_column(Text, nullable=False)
    section_order: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=text("NOW()"))

    brief: Mapped["AnalystBrief"] = relationship(back_populates="sections")
