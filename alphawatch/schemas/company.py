"""Company request/response schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CompanyResponse(BaseModel):
    """Company data returned from API endpoints.

    Attributes:
        id: Company UUID.
        ticker: Stock ticker symbol.
        name: Company display name.
        sector: Industry sector, if known.
        cik: SEC EDGAR CIK identifier, if known.
        created_at: Record creation timestamp.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ticker: str
    name: str
    sector: str | None = None
    cik: str | None = None
    created_at: datetime


class CompanyResolveResponse(BaseModel):
    """Response for the company resolution endpoint.

    Attributes:
        results: List of matching companies.
        query: The original search query.
    """

    results: list[CompanyResponse]
    query: str
