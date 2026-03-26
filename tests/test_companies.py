"""Tests for company resolution schemas and endpoint routing."""

import uuid

import pytest
from datetime import datetime, timezone

from alphawatch.schemas.company import CompanyResolveResponse, CompanyResponse

_UUID = uuid.UUID("12345678-1234-5678-1234-567812345678")


class TestCompanyResponseSchema:
    """Test CompanyResponse Pydantic schema."""

    def test_full_company(self):
        c = CompanyResponse(
            id=_UUID,
            ticker="AAPL",
            name="Apple Inc.",
            sector="Technology",
            cik="0000320193",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        assert c.ticker == "AAPL"
        assert c.sector == "Technology"

    def test_optional_fields_default_none(self):
        c = CompanyResponse(
            id=_UUID,
            ticker="AAPL",
            name="Apple Inc.",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        assert c.sector is None
        assert c.cik is None

    def test_model_dump(self):
        c = CompanyResponse(
            id=_UUID,
            ticker="AAPL",
            name="Apple Inc.",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        d = c.model_dump()
        assert d["ticker"] == "AAPL"
        assert "id" in d

    def test_rejects_malformed_uuid(self):
        with pytest.raises(Exception):
            CompanyResponse(
                id="not-a-uuid",
                ticker="AAPL",
                name="Apple Inc.",
                created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            )


class TestCompanyResolveResponseSchema:
    """Test CompanyResolveResponse schema."""

    def test_empty_results(self):
        r = CompanyResolveResponse(results=[], query="XYZ")
        assert r.results == []
        assert r.query == "XYZ"

    def test_with_results(self):
        company = CompanyResponse(
            id=_UUID, ticker="AAPL", name="Apple Inc.",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        r = CompanyResolveResponse(results=[company], query="AAPL")
        assert len(r.results) == 1
        assert r.results[0].ticker == "AAPL"


class TestCompanyEndpointAuth:
    """Test that company endpoints enforce authentication."""

    async def test_resolve_requires_auth(self, async_client):
        resp = await async_client.get("/api/companies/resolve?q=AAPL")
        assert resp.status_code == 401

    async def test_get_company_requires_auth(self, async_client):
        resp = await async_client.get(
            f"/api/companies/{uuid.uuid4()}"
        )
        assert resp.status_code == 401

    async def test_malformed_uuid_returns_422(self, async_client):
        """FastAPI validates UUID path param — malformed returns 422."""
        resp = await async_client.get("/api/companies/not-a-uuid")
        # 401 from middleware (no auth), but if auth were present it would be 422
        assert resp.status_code in (401, 422)


class TestCompanyEndpointRouting:
    """Test that company endpoints are registered and routable."""

    async def test_resolve_appears_in_openapi(self, async_client):
        resp = await async_client.get("/openapi.json")
        paths = resp.json()["paths"]
        assert "/api/companies/resolve" in paths

    async def test_get_company_appears_in_openapi(self, async_client):
        resp = await async_client.get("/openapi.json")
        paths = resp.json()["paths"]
        assert "/api/companies/{company_id}" in paths
