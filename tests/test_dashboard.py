"""Tests for dashboard endpoint: schemas, change_score, auth, routing."""

import uuid
from datetime import datetime, timezone

import pytest

from alphawatch.repositories.dashboard import _compute_change_score
from alphawatch.schemas.dashboard import CompanyCard, DashboardResponse


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

_UUID = uuid.UUID("12345678-1234-5678-1234-567812345678")
_NOW = datetime(2026, 3, 27, tzinfo=timezone.utc)


class TestCompanyCardSchema:
    """Test CompanyCard Pydantic schema."""

    def test_full_card(self):
        card = CompanyCard(
            company_id=_UUID,
            ticker="AAPL",
            name="Apple Inc.",
            sector="Technology",
            price=182.5,
            price_change_pct=2.3,
            sentiment_score=42,
            sentiment_delta=5,
            new_filings_count=2,
            risk_flag_count=1,
            risk_flag_max_severity="high",
            last_updated_at=_NOW,
            brief_id=_UUID,
            change_score=120.6,
        )
        assert card.ticker == "AAPL"
        assert card.change_score == 120.6

    def test_minimal_card(self):
        card = CompanyCard(
            company_id=_UUID,
            ticker="MSFT",
            name="Microsoft Corp.",
        )
        assert card.price is None
        assert card.change_score == 0.0
        assert card.new_filings_count == 0

    def test_model_dump(self):
        card = CompanyCard(
            company_id=_UUID,
            ticker="AAPL",
            name="Apple Inc.",
        )
        d = card.model_dump()
        assert "ticker" in d
        assert "change_score" in d


class TestDashboardResponseSchema:
    """Test DashboardResponse schema."""

    def test_empty_dashboard(self):
        resp = DashboardResponse(
            cards=[],
            as_of=_NOW,
            total=0,
        )
        assert resp.total == 0
        assert resp.time_range == "7d"

    def test_with_cards(self):
        card = CompanyCard(
            company_id=_UUID,
            ticker="AAPL",
            name="Apple Inc.",
            change_score=100.0,
        )
        resp = DashboardResponse(
            cards=[card],
            as_of=_NOW,
            time_range="24h",
            total=1,
        )
        assert resp.total == 1
        assert resp.time_range == "24h"


# ---------------------------------------------------------------------------
# Change score computation
# ---------------------------------------------------------------------------


class TestChangeScore:
    """Test _compute_change_score function."""

    def test_all_zeros(self):
        assert _compute_change_score(0, 0, None, None) == 0.0

    def test_filings_weight(self):
        # 2 filings × 30 = 60
        assert _compute_change_score(2, 0, None, None) == 60.0

    def test_risk_weight(self):
        # 3 risks × 25 = 75
        assert _compute_change_score(0, 3, None, None) == 75.0

    def test_price_weight(self):
        # |5.0| × 2 = 10
        assert _compute_change_score(0, 0, 5.0, None) == 10.0

    def test_negative_price_uses_abs(self):
        # |-3.5| × 2 = 7.0
        assert _compute_change_score(0, 0, -3.5, None) == 7.0

    def test_sentiment_weight(self):
        # |42| × 1 = 42
        assert _compute_change_score(0, 0, None, 42) == 42.0

    def test_composite(self):
        # 1×30 + 2×25 + |3.0|×2 + |10|×1 = 30+50+6+10 = 96
        assert _compute_change_score(1, 2, 3.0, 10) == 96.0


# ---------------------------------------------------------------------------
# Auth enforcement
# ---------------------------------------------------------------------------


class TestDashboardEndpointAuth:
    """Test dashboard endpoint enforces authentication."""

    async def test_dashboard_requires_auth(self, async_client):
        resp = await async_client.get("/api/dashboard")
        assert resp.status_code == 401

    async def test_dashboard_with_time_range_requires_auth(self, async_client):
        resp = await async_client.get("/api/dashboard?time_range=24h")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Routing / OpenAPI
# ---------------------------------------------------------------------------


class TestDashboardEndpointRouting:
    """Test dashboard endpoint is registered and routable."""

    async def test_dashboard_in_openapi(self, async_client):
        resp = await async_client.get("/openapi.json")
        paths = resp.json()["paths"]
        assert "/api/dashboard" in paths

    async def test_dashboard_is_get(self, async_client):
        resp = await async_client.get("/openapi.json")
        methods = resp.json()["paths"]["/api/dashboard"]
        assert "get" in methods

    async def test_dashboard_has_time_range_param(self, async_client):
        resp = await async_client.get("/openapi.json")
        endpoint = resp.json()["paths"]["/api/dashboard"]["get"]
        param_names = [p["name"] for p in endpoint.get("parameters", [])]
        assert "time_range" in param_names
