"""Financial snapshot request/response schemas."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class FinancialSnapshotResponse(BaseModel):
    """Financial snapshot data returned from API endpoints.

    Attributes:
        id: Snapshot UUID.
        company_id: Company UUID.
        snapshot_date: Date of the snapshot.
        price: Stock price.
        price_change_pct: Percent change.
        market_cap: Market capitalization.
        pe_ratio: Price-to-earnings ratio.
        debt_to_equity: Debt-to-equity ratio.
        analyst_rating: Analyst consensus rating.
        created_at: Record creation timestamp.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    company_id: str
    snapshot_date: date
    price: Decimal | None = None
    price_change_pct: Decimal | None = None
    market_cap: int | None = None
    pe_ratio: Decimal | None = None
    debt_to_equity: Decimal | None = None
    analyst_rating: str | None = None
    created_at: datetime


class SnapshotRefreshRequest(BaseModel):
    """Request body for refreshing a company's financial snapshot.

    Attributes:
        ticker: Stock ticker symbol.
    """

    ticker: str


class SnapshotRefreshResponse(BaseModel):
    """Response after refreshing a financial snapshot.

    Attributes:
        status: Refresh status.
        ticker: The ticker symbol.
        snapshot_date: The date of the refreshed snapshot.
        message: Human-readable status message.
    """

    status: str
    ticker: str
    snapshot_date: date | None = None
    message: str
