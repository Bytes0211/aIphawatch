"""Dashboard request/response schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class CompanyCard(BaseModel):
    """Summary card for a single company on the dashboard.

    Attributes:
        company_id: Company UUID.
        ticker: Stock ticker symbol.
        name: Company display name.
        sector: Industry sector.
        price: Latest stock price.
        price_change_pct: Percent change from prior snapshot.
        sentiment_score: Aggregate sentiment (-100 to +100), if available.
        sentiment_delta: Change in sentiment vs prior period.
        new_filings_count: Number of new filings since last login.
        risk_flag_count: Number of active risk flags.
        risk_flag_max_severity: Highest severity among active flags.
        last_updated_at: Most recent data update timestamp.
        brief_id: UUID of the latest brief, if any.
        change_score: Composite change signal for sorting.
    """

    company_id: uuid.UUID
    ticker: str
    name: str
    sector: str | None = None
    price: float | None = None
    price_change_pct: float | None = None
    sentiment_score: int | None = None
    sentiment_delta: int | None = None
    new_filings_count: int = 0
    risk_flag_count: int = 0
    risk_flag_max_severity: str | None = None
    last_updated_at: datetime | None = None
    brief_id: uuid.UUID | None = None
    change_score: float = 0.0


class DashboardResponse(BaseModel):
    """Response for the dashboard watchlist digest.

    Attributes:
        cards: List of company cards sorted by change_score descending.
        as_of: Timestamp when the dashboard was generated.
        time_range: Period covered (since_last_login, 24h, 7d).
        total: Total number of watched companies.
    """

    cards: list[CompanyCard]
    as_of: datetime
    time_range: str = "7d"
    total: int
