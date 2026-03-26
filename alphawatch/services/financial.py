"""Alpha Vantage financial data service.

Provides price quotes and company fundamentals via the Alpha Vantage API.
Free tier: 25 requests/day. For production, upgrade to premium or switch
to Polygon.io.
"""

import logging
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from alphawatch.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class QuoteData:
    """Parsed price quote from Alpha Vantage GLOBAL_QUOTE.

    Attributes:
        price: Latest stock price.
        price_change_pct: Percent change from prior close.
        volume: Trading volume.
        latest_trading_day: Date of the quote.
        raw: Full API response for storage in raw_data JSONB.
    """

    price: Decimal | None
    price_change_pct: Decimal | None
    volume: int | None
    latest_trading_day: date | None
    raw: dict[str, Any]


@dataclass
class OverviewData:
    """Parsed company fundamentals from Alpha Vantage OVERVIEW.

    Attributes:
        market_cap: Market capitalization.
        pe_ratio: Price-to-earnings ratio.
        debt_to_equity: Debt-to-equity ratio.
        analyst_rating: Analyst target price or rating string.
        sector: Company sector.
        raw: Full API response for storage in raw_data JSONB.
    """

    market_cap: int | None
    pe_ratio: Decimal | None
    debt_to_equity: Decimal | None
    analyst_rating: str | None
    sector: str | None
    raw: dict[str, Any]


def _safe_decimal(value: Any) -> Decimal | None:
    """Safely parse a value to Decimal, returning None on failure.

    Args:
        value: The raw value from the API response.

    Returns:
        Decimal if parseable, otherwise None.
    """
    if value is None or value == "None" or value == "-":
        return None
    try:
        return Decimal(str(value).replace("%", ""))
    except (InvalidOperation, ValueError):
        return None


def _safe_int(value: Any) -> int | None:
    """Safely parse a value to int, returning None on failure.

    Args:
        value: The raw value from the API response.

    Returns:
        Integer if parseable, otherwise None.
    """
    if value is None or value == "None" or value == "-":
        return None
    try:
        return int(float(str(value).replace(",", "")))
    except (ValueError, TypeError):
        return None


class AlphaVantageClient:
    """Async client for the Alpha Vantage financial data API.

    Args:
        api_key: Alpha Vantage API key.
        base_url: API base URL.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        settings = get_settings()
        self._api_key = api_key or settings.alpha_vantage_api_key
        self._base_url = base_url or settings.alpha_vantage_base_url
        if not self._api_key:
            logger.warning("Alpha Vantage API key not configured")

    async def get_quote(self, ticker: str) -> QuoteData:
        """Fetch the latest price quote for a ticker.

        Uses the GLOBAL_QUOTE function.

        Args:
            ticker: Stock ticker symbol.

        Returns:
            Parsed quote data with price and change percentage.
        """
        params = {
            "function": "GLOBAL_QUOTE",
            "symbol": ticker.upper(),
            "apikey": self._api_key,
        }
        data = await self._request(params)
        quote = data.get("Global Quote", {})

        trading_day = None
        raw_date = quote.get("07. latest trading day")
        if raw_date:
            try:
                trading_day = date.fromisoformat(raw_date)
            except ValueError:
                pass

        return QuoteData(
            price=_safe_decimal(quote.get("05. price")),
            price_change_pct=_safe_decimal(quote.get("10. change percent")),
            volume=_safe_int(quote.get("06. volume")),
            latest_trading_day=trading_day,
            raw=data,
        )

    async def get_overview(self, ticker: str) -> OverviewData:
        """Fetch company fundamentals for a ticker.

        Uses the OVERVIEW function for P/E, debt/equity, analyst rating.

        Args:
            ticker: Stock ticker symbol.

        Returns:
            Parsed overview data with financial metrics.
        """
        params = {
            "function": "OVERVIEW",
            "symbol": ticker.upper(),
            "apikey": self._api_key,
        }
        data = await self._request(params)

        return OverviewData(
            market_cap=_safe_int(data.get("MarketCapitalization")),
            pe_ratio=_safe_decimal(data.get("PERatio")),
            debt_to_equity=_safe_decimal(data.get("DebtToEquityRatio")),
            analyst_rating=data.get("AnalystTargetPrice"),
            sector=data.get("Sector"),
            raw=data,
        )

    async def fetch_snapshot(self, ticker: str) -> dict[str, Any]:
        """Fetch a complete financial snapshot combining quote + overview.

        Issues GLOBAL_QUOTE and OVERVIEW requests concurrently via
        ``asyncio.gather`` to halve wall-clock latency.

        Args:
            ticker: Stock ticker symbol.

        Returns:
            Dict with all snapshot fields ready for repository upsert.
        """
        import asyncio

        quote, overview = await asyncio.gather(
            self.get_quote(ticker),
            self.get_overview(ticker),
        )

        return {
            "snapshot_date": quote.latest_trading_day or date.today(),
            "price": quote.price,
            "price_change_pct": quote.price_change_pct,
            "market_cap": overview.market_cap,
            "pe_ratio": overview.pe_ratio,
            "debt_to_equity": overview.debt_to_equity,
            "analyst_rating": overview.analyst_rating,
            "raw_data": {
                "quote": quote.raw,
                "overview": overview.raw,
            },
        }

    async def _request(self, params: dict[str, str]) -> dict[str, Any]:
        """Make a request to the Alpha Vantage API.

        Args:
            params: Query parameters including function and apikey.

        Returns:
            Parsed JSON response.

        Raises:
            httpx.HTTPStatusError: On HTTP errors.
            ValueError: If the API returns an error message.
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(self._base_url, params=params)
            resp.raise_for_status()
            data = resp.json()

        # Alpha Vantage returns errors in the response body, not HTTP status
        if "Error Message" in data:
            raise ValueError(f"Alpha Vantage error: {data['Error Message']}")
        if "Note" in data:
            raise ValueError(f"Alpha Vantage rate limit reached: {data['Note']}")
        if "Information" in data:
            raise ValueError(f"Alpha Vantage plan restriction: {data['Information']}")

        return data
