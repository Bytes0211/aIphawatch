"""Financial snapshot and sentiment record ORM models."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Date, ForeignKey, Index, Integer, Numeric, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from alphawatch.database import Base


class FinancialSnapshot(Base):
    """Point-in-time financial metrics for a company.

    Attributes:
        id: Primary key UUID.
        company_id: FK to companies.
        snapshot_date: Date of the snapshot.
        price: Current stock price.
        price_change_pct: Percent change since prior snapshot.
        market_cap: Market capitalization in dollars.
        pe_ratio: Price-to-earnings ratio.
        debt_to_equity: Debt-to-equity ratio.
        analyst_rating: Consensus analyst rating string.
        raw_data: JSONB full API response.
        created_at: Record creation timestamp.
    """

    __tablename__ = "financial_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "company_id", "snapshot_date", name="uq_snapshots_company_date"
        ),
        Index("idx_snapshots_company", "company_id", "snapshot_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False
    )
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    price_change_pct: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 4), nullable=True
    )
    market_cap: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    pe_ratio: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    debt_to_equity: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 4), nullable=True
    )
    analyst_rating: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_data: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(server_default=text("NOW()"))


class SentimentRecord(Base):
    """Sentiment score for a document.

    Attributes:
        id: Primary key UUID.
        company_id: FK to companies.
        document_id: FK to documents.
        score: Sentiment score from -100 to +100.
        source_type: Type of source scored.
        scored_at: Timestamp when scored.
    """

    __tablename__ = "sentiment_records"
    __table_args__ = (
        Index("idx_sentiment_company", "company_id", "scored_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False
    )
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    scored_at: Mapped[datetime] = mapped_column(server_default=text("NOW()"))
