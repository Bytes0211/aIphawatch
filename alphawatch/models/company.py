"""Company ORM model."""

import uuid
from datetime import datetime

from sqlalchemy import Index, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from alphawatch.database import Base


class Company(Base):
    """Globally shared company entity.

    Companies are NOT tenant-scoped. AAPL is shared across all tenants.
    Tenant isolation is enforced through watchlist joins.

    Attributes:
        id: Primary key UUID.
        ticker: Unique stock ticker symbol.
        name: Company display name.
        sector: Industry sector.
        cik: SEC EDGAR CIK identifier.
        metadata: JSONB for additional company data.
        created_at: Record creation timestamp.
        updated_at: Last modification timestamp.
    """

    __tablename__ = "companies"
    __table_args__ = (
        Index("idx_companies_ticker", "ticker"),
        Index("idx_companies_cik", "cik"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    ticker: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    sector: Mapped[str | None] = mapped_column(Text, nullable=True)
    cik: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("NOW()"), onupdate=text("NOW()"))
