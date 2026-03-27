"""Analyst brief request/response Pydantic schemas."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class BriefSectionResponse(BaseModel):
    """A single section within an analyst brief.

    Attributes:
        id: Section UUID.
        section_type: One of snapshot, what_changed, risk_flags, sentiment,
            sources, executive_summary, suggested_followups.
        section_order: Display ordering integer (1-based).
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
        company_id: UUID of the company this brief covers.
        user_id: UUID of the user who requested generation.
        session_id: UUID linking this brief to its generation session.
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
    """Lightweight brief summary — metadata only, no sections.

    Used for listing recent briefs without pulling full section content.

    Attributes:
        id: Brief UUID.
        company_id: UUID of the associated company.
        generated_at: Timestamp of brief generation.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    generated_at: datetime


class BriefGenerateRequest(BaseModel):
    """Optional request body for triggering brief generation.

    Attributes:
        query_text: Optional seed query to focus chunk retrieval.
            When omitted, a broad company-overview query is used.
    """

    query_text: str | None = None


class BriefGenerateResponse(BaseModel):
    """Response after triggering brief generation.

    Attributes:
        status: One of 'completed', 'completed_with_errors'.
        brief_id: UUID string of the generated brief (empty on failure).
        company_id: UUID string of the company.
        ticker: Stock ticker symbol.
        message: Human-readable status description.
    """

    status: str
    brief_id: str
    company_id: str
    ticker: str
    message: str
