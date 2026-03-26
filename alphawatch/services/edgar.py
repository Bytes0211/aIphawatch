"""SEC EDGAR full-text search API client."""

import asyncio
import logging
from typing import Any

import httpx

from alphawatch.agents.state import FilingRef
from alphawatch.config import get_settings

logger = logging.getLogger(__name__)

# Map EDGAR filing types to our source_type enum
FILING_TYPE_MAP: dict[str, str] = {
    "10-K": "edgar_10k",
    "10-Q": "edgar_10q",
    "8-K": "edgar_8k",
}


class EdgarClient:
    """Async client for the SEC EDGAR full-text search API.

    Respects SEC rate limits (10 req/sec) and sets the required
    User-Agent header per SEC policy. Uses a shared httpx.AsyncClient
    for connection pooling across multiple requests.

    Args:
        user_agent: User-Agent string for SEC compliance.
        base_url: EDGAR API base URL.
        rate_limit: Maximum requests per second.
    """

    def __init__(
        self,
        user_agent: str | None = None,
        base_url: str | None = None,
        rate_limit: float | None = None,
    ) -> None:
        settings = get_settings()
        self._user_agent = user_agent or settings.edgar_user_agent
        self._base_url = base_url or settings.edgar_base_url
        self._rate_limit = rate_limit or settings.edgar_rate_limit
        self._semaphore = asyncio.Semaphore(int(self._rate_limit))
        self._client = httpx.AsyncClient(
            headers={"User-Agent": self._user_agent},
            timeout=60.0,
        )

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    async def search_filings(
        self,
        ticker: str,
        filing_types: list[str] | None = None,
        start_date: str | None = None,
        cik: str | None = None,
    ) -> list[FilingRef]:
        """Search EDGAR for filings matching a ticker.

        If a CIK is provided, it is used to filter results to the
        specific filer, avoiding false matches from competitor filings
        that mention the ticker.

        Args:
            ticker: Stock ticker symbol.
            filing_types: Filing types to search for (e.g. ["10-K", "10-Q"]).
                Defaults to ["10-K", "10-Q", "8-K"].
            start_date: Only return filings after this date (YYYY-MM-DD).
            cik: SEC CIK number to filter to a specific filer.

        Returns:
            List of FilingRef objects for discovered filings.
        """
        if filing_types is None:
            filing_types = ["10-K", "10-Q", "8-K"]

        query = f'"{ticker}"'
        params: dict[str, str] = {
            "q": query,
            "forms": ",".join(filing_types),
        }
        if start_date:
            params["dateRange"] = "custom"
            params["startdt"] = start_date
        if cik:
            params["ciks"] = cik

        async with self._semaphore:
            resp = await self._client.get(
                f"{self._base_url}/search-index",
                params=params,
            )
            resp.raise_for_status()
            data = resp.json()

        filings: list[FilingRef] = []
        for hit in data.get("hits", {}).get("hits", []):
            source = hit.get("_source", {})
            filing_type = source.get("forms", "")
            if filing_type not in FILING_TYPE_MAP:
                continue

            accession = source.get("file_num", source.get("accession_no", ""))
            filings.append(
                FilingRef(
                    accession_number=accession,
                    filing_type=filing_type,
                    filing_date=source.get("file_date", ""),
                    title=source.get("display_names", [ticker])[0]
                    if source.get("display_names")
                    else f"{ticker} {filing_type}",
                    url=self._build_filing_url(source),
                )
            )

        logger.info(
            "EDGAR search: ticker=%s types=%s found=%d",
            ticker, filing_types, len(filings),
        )
        return filings

    async def download_filing_text(self, url: str) -> str:
        """Download the text content of a filing.

        Args:
            url: URL to the filing document.

        Returns:
            The raw text content of the filing.
        """
        async with self._semaphore:
            resp = await self._client.get(url)
            resp.raise_for_status()
            return resp.text

    @staticmethod
    def _build_filing_url(source: dict[str, Any]) -> str:
        """Build the EDGAR filing URL from search result source.

        Args:
            source: The _source dict from an EDGAR search hit.

        Returns:
            Full URL to the filing document.
        """
        file_name = source.get("file_name", "")
        if file_name.startswith("http"):
            return file_name
        return f"https://www.sec.gov/Archives/edgar/data/{file_name}"

    @staticmethod
    def map_filing_type(edgar_type: str) -> str:
        """Map an EDGAR filing type to our source_type enum.

        Args:
            edgar_type: EDGAR filing type string (e.g. "10-K").

        Returns:
            Source type string for the database.

        Raises:
            ValueError: If the filing type is not recognized.
        """
        mapped = FILING_TYPE_MAP.get(edgar_type)
        if not mapped:
            raise ValueError(f"Unknown EDGAR filing type: {edgar_type}")
        return mapped
