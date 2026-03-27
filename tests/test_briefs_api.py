"""Tests for briefs API endpoints: schemas, auth, and routing."""

import uuid
from datetime import datetime, timezone
from typing import Any

import pytest

from alphawatch.schemas.brief import (
    BriefGenerateRequest,
    BriefGenerateResponse,
    BriefResponse,
    BriefSectionResponse,
    BriefSummaryResponse,
)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

_UUID = uuid.UUID("12345678-1234-5678-1234-567812345678")
_NOW = datetime(2026, 3, 26, tzinfo=timezone.utc)


class TestBriefSectionResponseSchema:
    """Test BriefSectionResponse schema."""

    def test_full_section(self):
        s = BriefSectionResponse(
            id=_UUID,
            section_type="snapshot",
            section_order=1,
            content={"price": 182.5, "available": True},
            created_at=_NOW,
        )
        assert s.section_type == "snapshot"
        assert s.section_order == 1
        assert s.content["price"] == 182.5

    def test_model_dump(self):
        s = BriefSectionResponse(
            id=_UUID,
            section_type="executive_summary",
            section_order=6,
            content={"summary": "Test summary."},
            created_at=_NOW,
        )
        d = s.model_dump()
        assert d["section_type"] == "executive_summary"
        assert "id" in d


class TestBriefResponseSchema:
    """Test BriefResponse schema."""

    def test_full_brief(self):
        section = BriefSectionResponse(
            id=_UUID,
            section_type="snapshot",
            section_order=1,
            content={"available": True},
            created_at=_NOW,
        )
        b = BriefResponse(
            id=_UUID,
            company_id=_UUID,
            user_id=_UUID,
            session_id=_UUID,
            generated_at=_NOW,
            sections=[section],
        )
        assert len(b.sections) == 1
        assert b.generated_at == _NOW

    def test_empty_sections(self):
        b = BriefResponse(
            id=_UUID,
            company_id=_UUID,
            user_id=_UUID,
            session_id=_UUID,
            generated_at=_NOW,
        )
        assert b.sections == []


class TestBriefSummaryResponseSchema:
    """Test BriefSummaryResponse schema."""

    def test_summary(self):
        s = BriefSummaryResponse(
            id=_UUID,
            company_id=_UUID,
            generated_at=_NOW,
        )
        assert s.id == _UUID


class TestBriefGenerateRequestSchema:
    """Test BriefGenerateRequest schema."""

    def test_defaults(self):
        r = BriefGenerateRequest()
        assert r.query_text is None

    def test_with_query(self):
        r = BriefGenerateRequest(query_text="Apple debt covenants")
        assert r.query_text == "Apple debt covenants"


class TestBriefGenerateResponseSchema:
    """Test BriefGenerateResponse schema."""

    def test_success(self):
        r = BriefGenerateResponse(
            status="completed",
            brief_id=str(_UUID),
            company_id=str(_UUID),
            ticker="AAPL",
            message="Brief generated successfully",
        )
        assert r.status == "completed"
        assert "AAPL" == r.ticker


# ---------------------------------------------------------------------------
# Auth enforcement
# ---------------------------------------------------------------------------


class TestBriefEndpointAuth:
    """Test that brief endpoints enforce authentication."""

    async def test_get_latest_requires_auth(self, async_client):
        resp = await async_client.get(f"/api/companies/{uuid.uuid4()}/brief")
        assert resp.status_code == 401

    async def test_generate_requires_auth(self, async_client):
        resp = await async_client.post(
            f"/api/companies/{uuid.uuid4()}/brief/generate"
        )
        assert resp.status_code == 401

    async def test_get_sections_requires_auth(self, async_client):
        resp = await async_client.get(
            f"/api/companies/{uuid.uuid4()}/brief/{uuid.uuid4()}/sections"
        )
        assert resp.status_code == 401

    async def test_list_briefs_requires_auth(self, async_client):
        resp = await async_client.get(
            f"/api/companies/{uuid.uuid4()}/briefs"
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Routing / OpenAPI
# ---------------------------------------------------------------------------


class TestBriefEndpointRouting:
    """Test that brief endpoints are registered and routable."""

    async def test_get_latest_in_openapi(self, async_client):
        resp = await async_client.get("/openapi.json")
        paths = resp.json()["paths"]
        assert "/api/companies/{company_id}/brief" in paths

    async def test_generate_in_openapi(self, async_client):
        resp = await async_client.get("/openapi.json")
        paths = resp.json()["paths"]
        assert "/api/companies/{company_id}/brief/generate" in paths
        methods = paths["/api/companies/{company_id}/brief/generate"]
        assert "post" in methods

    async def test_sections_in_openapi(self, async_client):
        resp = await async_client.get("/openapi.json")
        paths = resp.json()["paths"]
        assert "/api/companies/{company_id}/brief/{brief_id}/sections" in paths

    async def test_list_briefs_in_openapi(self, async_client):
        resp = await async_client.get("/openapi.json")
        paths = resp.json()["paths"]
        assert "/api/companies/{company_id}/briefs" in paths
        methods = paths["/api/companies/{company_id}/briefs"]
        assert "get" in methods
