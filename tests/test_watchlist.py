"""Tests for watchlist CRUD schemas and endpoint routing."""

import uuid

import pytest
from datetime import datetime, timezone

from alphawatch.schemas.company import CompanyResponse
from alphawatch.schemas.watchlist import (
    WatchlistAddRequest,
    WatchlistEntryResponse,
    WatchlistResponse,
)

_CID = uuid.UUID("11111111-1111-1111-1111-111111111111")
_WID = uuid.UUID("22222222-2222-2222-2222-222222222222")


class TestWatchlistAddRequestSchema:
    """Test WatchlistAddRequest schema."""

    def test_valid_request(self):
        r = WatchlistAddRequest(ticker="AAPL")
        assert r.ticker == "AAPL"

    def test_model_dump(self):
        r = WatchlistAddRequest(ticker="msft")
        assert r.model_dump() == {"ticker": "msft"}


class TestWatchlistEntryResponseSchema:
    """Test WatchlistEntryResponse schema."""

    def test_full_entry(self):
        company = CompanyResponse(
            id=_CID, ticker="AAPL", name="Apple Inc.",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        entry = WatchlistEntryResponse(
            id=_WID, company=company,
            created_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        )
        assert entry.company.ticker == "AAPL"
        assert entry.id == _WID


class TestWatchlistResponseSchema:
    """Test WatchlistResponse schema."""

    def test_empty_watchlist(self):
        r = WatchlistResponse(entries=[], count=0)
        assert r.count == 0
        assert r.entries == []

    def test_with_entries(self):
        company = CompanyResponse(
            id=_CID, ticker="AAPL", name="Apple Inc.",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        entry = WatchlistEntryResponse(
            id=_WID, company=company,
            created_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        )
        r = WatchlistResponse(entries=[entry], count=1)
        assert r.count == 1
        assert r.entries[0].company.ticker == "AAPL"


class TestWatchlistEndpointAuth:
    """Test that watchlist endpoints enforce authentication."""

    async def test_list_requires_auth(self, async_client):
        resp = await async_client.get("/api/watchlist")
        assert resp.status_code == 401

    async def test_add_requires_auth(self, async_client):
        resp = await async_client.post(
            "/api/watchlist", json={"ticker": "AAPL"}
        )
        assert resp.status_code == 401

    async def test_delete_requires_auth(self, async_client):
        resp = await async_client.delete("/api/watchlist/some-uuid")
        assert resp.status_code == 401


class TestWatchlistEndpointRouting:
    """Test that watchlist endpoints are registered and routable."""

    async def test_list_appears_in_openapi(self, async_client):
        resp = await async_client.get("/openapi.json")
        paths = resp.json()["paths"]
        assert "/api/watchlist" in paths

    async def test_delete_appears_in_openapi(self, async_client):
        resp = await async_client.get("/openapi.json")
        paths = resp.json()["paths"]
        assert "/api/watchlist/{company_id}" in paths

    async def test_list_has_get_and_post(self, async_client):
        resp = await async_client.get("/openapi.json")
        methods = resp.json()["paths"]["/api/watchlist"]
        assert "get" in methods
        assert "post" in methods

    async def test_delete_has_delete_method(self, async_client):
        resp = await async_client.get("/openapi.json")
        methods = resp.json()["paths"]["/api/watchlist/{company_id}"]
        assert "delete" in methods
