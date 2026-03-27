"""Analyst brief request/response schemas."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class BriefSectionResponse(BaseModel):
    """A single section within an analyst brief.

    Attributes:
        id: Section UUID.
        section_type: Section identifier (snapshot, what_changed, etc.).
        section_order: Display ordering (1-based).
        content: JSONB section payload (schema varies by type).
        created_at: Record creation timestamp.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    section_type: str
    section_order: int
    content: dict[str, Any]
    created_at: datetime


class BriefResponse(BaseModel):
    """Full analyst brief with all sections.

    Attributes:
        id: Brief UUID.
        company_id: Company UUID.
        user_id: User UUID who requested the brief.
        session_id: Generation session UUID.
        generated_at: Timestamp of brief generation.
        sections: Ordered list of brief sections.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    user_id: uuid.UUID
    session_id: uuid.UUID
    generated_at: datetime
    sections: list[BriefSectionResponse] = []


class BriefSummaryResponse(BaseModel):
    """Brief metadata without sections (for listing).

    Attributes:
        id: Brief UUID.
        company_id: Company UUID.
        generated_at: Timestamp of brief generation.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    generated_at: datetime


class BriefGenerateRequest(BaseModel):
    """Request body for force-generating a new brief.

    Attributes:
        query_text: Optional custom query to seed chunk retrieval.
    """

    query_text: str | None = None


class BriefGenerateResponse(BaseModel):
    """Response after triggering brief generation.

    Attributes:
        status: Generation status.
        brief_id: UUID of the generated brief (empty on failure).
        company_id: Company UUID.
        ticker: Ticker symbol.
        message: Human-readable status message.
    """

    status: str
    brief_id: str
    company_id: str
    ticker: str
    message: str
