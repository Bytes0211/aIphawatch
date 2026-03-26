"""Watchlist request/response schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from alphawatch.schemas.company import CompanyResponse


class WatchlistAddRequest(BaseModel):
    """Request body for adding a company to the watchlist.

    Attributes:
        ticker: Stock ticker symbol to add (resolved to company).
    """

    ticker: str


class WatchlistEntryResponse(BaseModel):
    """Single watchlist entry with nested company data.

    Attributes:
        id: Watchlist entry UUID.
        company: The watched company.
        created_at: When the company was added to the watchlist.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company: CompanyResponse
    created_at: datetime


class WatchlistResponse(BaseModel):
    """Response for listing the user's watchlist.

    Attributes:
        entries: List of watchlist entries with company data.
        count: Total number of entries.
    """

    entries: list[WatchlistEntryResponse]
    count: int
