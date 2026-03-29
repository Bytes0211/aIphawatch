"""Tests for financial API service, schemas, and helpers."""

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from alphawatch.services.financial import (
    AlphaVantageClient,
    FinancialDataProvider,
    OverviewData,
    QuoteData,
    _safe_decimal,
    _safe_int,
    get_financial_data_provider,
)
from alphawatch.schemas.financial import (
    FinancialSnapshotResponse,
    SnapshotRefreshRequest,
    SnapshotRefreshResponse,
)


# ---------------------------------------------------------------------------
# Safe parsing helpers
# ---------------------------------------------------------------------------
class TestSafeDecimal:
    """Test _safe_decimal helper."""

    def test_valid_number(self):
        assert _safe_decimal("182.45") == Decimal("182.45")

    def test_percentage_stripped(self):
        assert _safe_decimal("2.30%") == Decimal("2.30")

    def test_none_returns_none(self):
        assert _safe_decimal(None) is None

    def test_none_string_returns_none(self):
        assert _safe_decimal("None") is None

    def test_dash_returns_none(self):
        assert _safe_decimal("-") is None

    def test_invalid_returns_none(self):
        assert _safe_decimal("N/A") is None

    def test_zero(self):
        assert _safe_decimal("0") == Decimal("0")

    def test_negative(self):
        assert _safe_decimal("-1.5") == Decimal("-1.5")


class TestSafeInt:
    """Test _safe_int helper."""

    def test_valid_number(self):
        assert _safe_int("285000000000") == 285000000000

    def test_with_commas(self):
        assert _safe_int("2,850,000") == 2850000

    def test_none_returns_none(self):
        assert _safe_int(None) is None

    def test_none_string_returns_none(self):
        assert _safe_int("None") is None

    def test_dash_returns_none(self):
        assert _safe_int("-") is None

    def test_invalid_returns_none(self):
        assert _safe_int("abc") is None

    def test_float_string(self):
        """Alpha Vantage can return MarketCap as '285000000000.0'."""
        assert _safe_int("285000000000.0") == 285000000000

    def test_float_string_with_decimals(self):
        assert _safe_int("42.7") == 42


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
class TestQuoteData:
    """Test QuoteData dataclass."""

    def test_creation(self):
        q = QuoteData(
            price=Decimal("182.45"),
            price_change_pct=Decimal("2.30"),
            volume=45000000,
            latest_trading_day=date(2026, 3, 25),
            raw={"Global Quote": {}},
        )
        assert q.price == Decimal("182.45")
        assert q.latest_trading_day == date(2026, 3, 25)

    def test_nullable_fields(self):
        q = QuoteData(
            price=None,
            price_change_pct=None,
            volume=None,
            latest_trading_day=None,
            raw={},
        )
        assert q.price is None


class TestOverviewData:
    """Test OverviewData dataclass."""

    def test_creation(self):
        o = OverviewData(
            market_cap=2850000000000,
            pe_ratio=Decimal("28.4"),
            debt_to_equity=Decimal("1.73"),
            analyst_rating="Buy",
            sector="Technology",
            raw={},
        )
        assert o.sector == "Technology"
        assert o.pe_ratio == Decimal("28.4")


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class TestFinancialSnapshotResponse:
    """Test FinancialSnapshotResponse schema."""

    def test_full_snapshot(self):
        s = FinancialSnapshotResponse(
            id="snap-1",
            company_id="comp-1",
            snapshot_date=date(2026, 3, 25),
            price=Decimal("182.45"),
            market_cap=2850000000000,
            pe_ratio=Decimal("28.4"),
            created_at=datetime(2026, 3, 25, tzinfo=timezone.utc),
        )
        assert s.price == Decimal("182.45")
        assert s.snapshot_date == date(2026, 3, 25)

    def test_optional_fields_default_none(self):
        s = FinancialSnapshotResponse(
            id="snap-1",
            company_id="comp-1",
            snapshot_date=date(2026, 3, 25),
            created_at=datetime(2026, 3, 25, tzinfo=timezone.utc),
        )
        assert s.price is None
        assert s.analyst_rating is None


class TestSnapshotRefreshRequest:
    """Test SnapshotRefreshRequest schema."""

    def test_valid(self):
        r = SnapshotRefreshRequest(ticker="AAPL")
        assert r.ticker == "AAPL"


class TestSnapshotRefreshResponse:
    """Test SnapshotRefreshResponse schema."""

    def test_success(self):
        r = SnapshotRefreshResponse(
            status="completed",
            ticker="AAPL",
            snapshot_date=date(2026, 3, 25),
            message="Snapshot refreshed",
        )
        assert r.status == "completed"
        assert r.snapshot_date == date(2026, 3, 25)

    def test_without_date(self):
        r = SnapshotRefreshResponse(
            status="failed",
            ticker="AAPL",
            message="API key not configured",
        )
        assert r.snapshot_date is None


# ---------------------------------------------------------------------------
# Client instantiation
# ---------------------------------------------------------------------------
class TestAlphaVantageClient:
    """Test AlphaVantageClient initialization."""

    def test_creates_with_defaults(self):
        client = AlphaVantageClient()
        assert client._base_url == "https://www.alphavantage.co/query"

    def test_creates_with_custom_key(self):
        client = AlphaVantageClient(api_key="test-key")
        assert client._api_key == "test-key"

    def test_implements_provider_abstraction(self):
        client = AlphaVantageClient(api_key="test-key")
        assert isinstance(client, FinancialDataProvider)


class TestFinancialDataProviderFactory:
    """Test provider factory selection and validation."""

    def test_factory_returns_alpha_vantage_client(self):
        provider = get_financial_data_provider("alpha_vantage")
        assert isinstance(provider, AlphaVantageClient)

    def test_factory_rejects_unknown_provider(self):
        with pytest.raises(ValueError, match="Unsupported financial data provider"):
            get_financial_data_provider("unknown_provider")


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
class TestFinancialConfig:
    """Test Alpha Vantage config in Settings."""

    def test_defaults(self):
        from alphawatch.config import Settings

        s = Settings()
        assert s.financial_data_provider == "alpha_vantage"
        assert s.alpha_vantage_base_url == "https://www.alphavantage.co/query"
        assert s.alpha_vantage_daily_limit == 25
        assert s.alpha_vantage_api_key == ""
