"""NewsAPI client for fetching company news articles."""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from alphawatch.config import get_settings

logger = logging.getLogger(__name__)


class NewsArticle:
    """A news article from NewsAPI.

    Attributes:
        title: Article headline.
        description: Article excerpt/summary.
        url: URL to the full article.
        source_name: Name of the news source.
        published_at: ISO 8601 publication timestamp.
        content: Truncated article content (if available).
        author: Article author (if available).
    """

    def __init__(
        self,
        title: str,
        description: str | None,
        url: str,
        source_name: str,
        published_at: str,
        content: str | None = None,
        author: str | None = None,
    ) -> None:
        self.title = title
        self.description = description or ""
        self.url = url
        self.source_name = source_name
        self.published_at = published_at
        self.content = content or ""
        self.author = author


class NewsClient:
    """Async client for the NewsAPI service.

    Fetches recent news articles for a given company ticker or name.
    Respects the free-tier daily rate limit (100 requests/day).

    Args:
        api_key: NewsAPI API key.
        base_url: NewsAPI base URL.
        page_size: Number of articles to fetch per request.
        daily_limit: Maximum requests per day (free tier = 100).
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        page_size: int | None = None,
        daily_limit: int | None = None,
    ) -> None:
        settings = get_settings()
        self._api_key = api_key or settings.newsapi_api_key
        self._base_url = base_url or settings.newsapi_base_url
        self._page_size = page_size or settings.newsapi_page_size
        self._daily_limit = daily_limit or settings.newsapi_daily_limit
        self._client = httpx.AsyncClient(timeout=30.0)

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    async def search_articles(
        self,
        query: str,
        from_date: str | None = None,
        to_date: str | None = None,
        language: str = "en",
        sort_by: str = "publishedAt",
    ) -> list[NewsArticle]:
        """Search for news articles matching a query.

        Args:
            query: Search query (company name, ticker, or keywords).
            from_date: Start date for articles (YYYY-MM-DD).
                Defaults to 7 days ago.
            to_date: End date for articles (YYYY-MM-DD).
                Defaults to today.
            language: Language code (default: "en").
            sort_by: Sort order ("publishedAt", "relevancy", "popularity").

        Returns:
            List of NewsArticle objects.

        Raises:
            httpx.HTTPStatusError: If the API returns an error status.
            ValueError: If the API key is not configured.
        """
        if not self._api_key:
            raise ValueError(
                "NewsAPI API key not configured. Set NEWSAPI_API_KEY in environment."
            )

        # Default to last 7 days if no date range provided
        if not from_date:
            from_date = (datetime.now(UTC) - timedelta(days=7)).strftime("%Y-%m-%d")
        if not to_date:
            to_date = datetime.now(UTC).strftime("%Y-%m-%d")

        params: dict[str, Any] = {
            "q": query,
            "from": from_date,
            "to": to_date,
            "language": language,
            "sortBy": sort_by,
            "pageSize": self._page_size,
            "apiKey": self._api_key,
        }

        try:
            resp = await self._client.get(
                f"{self._base_url}/everything",
                params=params,
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("status") != "ok":
                error_msg = data.get("message", "Unknown error")
                raise ValueError(f"NewsAPI error: {error_msg}")

            articles = []
            for article_data in data.get("articles", []):
                # Skip articles with missing required fields
                if not article_data.get("title") or not article_data.get("url"):
                    continue

                articles.append(
                    NewsArticle(
                        title=article_data["title"],
                        description=article_data.get("description"),
                        url=article_data["url"],
                        source_name=article_data.get("source", {}).get(
                            "name", "Unknown"
                        ),
                        published_at=article_data.get("publishedAt", ""),
                        content=article_data.get("content"),
                        author=article_data.get("author"),
                    )
                )

            logger.info(
                "NewsAPI search: query=%s from=%s to=%s found=%d",
                query,
                from_date,
                to_date,
                len(articles),
            )
            return articles

        except httpx.HTTPStatusError as exc:
            logger.error("NewsAPI HTTP error: %s", exc)
            raise
        except Exception as exc:
            logger.error("NewsAPI search failed: %s", exc)
            raise

    async def get_company_news(
        self,
        ticker: str,
        company_name: str | None = None,
        days_back: int = 7,
    ) -> list[NewsArticle]:
        """Fetch recent news for a company.

        Searches using both ticker and company name (if provided)
        to maximize relevant results.

        Args:
            ticker: Stock ticker symbol.
            company_name: Full company name (optional, improves results).
            days_back: Number of days to look back (default: 7).

        Returns:
            List of NewsArticle objects sorted by publication date.
        """
        # Build search query with ticker and optional company name
        if company_name:
            query = f'"{ticker}" OR "{company_name}"'
        else:
            query = f'"{ticker}"'

        from_date = (datetime.now(UTC) - timedelta(days=days_back)).strftime("%Y-%m-%d")

        articles = await self.search_articles(
            query=query,
            from_date=from_date,
            sort_by="publishedAt",
        )

        # Deduplicate by URL (in case both ticker and name returned the same article)
        seen_urls = set()
        unique_articles = []
        for article in articles:
            if article.url not in seen_urls:
                seen_urls.add(article.url)
                unique_articles.append(article)

        return unique_articles
