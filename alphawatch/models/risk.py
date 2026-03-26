"""Risk flag ORM model."""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Index, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from alphawatch.database import Base


class RiskFlag(Base):
    """Detected risk signal for a company.

    Attributes:
        id: Primary key UUID.
        company_id: FK to companies.
        document_id: Optional FK to the source document.
        flag_type: One of covenant, litigation, guidance_cut,
            insider_sell, schema_drift.
        severity: One of low, medium, high, critical.
        description: Human-readable risk description.
        detected_at: Timestamp of detection.
    """

    __tablename__ = "risk_flags"
    __table_args__ = (
        Index("idx_risk_flags_company", "company_id", "detected_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False
    )
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=True
    )
    flag_type: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    detected_at: Mapped[datetime] = mapped_column(server_default=text("NOW()"))
