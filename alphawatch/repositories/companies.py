"""Company repository — resolution and lookup."""

import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from alphawatch.models.company import Company


class CompanyRepository:
    """Data access for the globally shared companies table.

    Companies are NOT tenant-scoped — AAPL is shared across all tenants.

    Args:
        session: An async SQLAlchemy session.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _escape_like(value: str) -> str:
        """Escape LIKE/ILIKE special characters in a search string.

        Args:
            value: Raw user input.

        Returns:
            Escaped string safe for use in LIKE/ILIKE patterns.
        """
        return value.replace("%", r"\%").replace("_", r"\_")

    async def resolve(self, query: str) -> list[Company]:
        """Resolve a ticker or company name to matching companies.

        Performs a case-insensitive prefix match on ticker and an
        ILIKE match on name. Special characters (%, _) are escaped.

        Args:
            query: Search string (ticker symbol or partial name).

        Returns:
            List of matching Company objects, ordered by ticker.
        """
        ticker_q = self._escape_like(query.strip().upper())
        name_q = self._escape_like(query.strip())
        stmt = (
            select(Company)
            .where(
                or_(
                    Company.ticker.ilike(f"{ticker_q}%"),
                    Company.name.ilike(f"%{name_q}%"),
                )
            )
            .order_by(Company.ticker)
            .limit(20)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, company_id: uuid.UUID) -> Company | None:
        """Get a company by its primary key.

        Args:
            company_id: The company UUID.

        Returns:
            The Company if found, otherwise None.
        """
        return await self._session.get(Company, company_id)

    async def get_by_ticker(self, ticker: str) -> Company | None:
        """Get a company by its ticker symbol.

        Args:
            ticker: The stock ticker (case-insensitive).

        Returns:
            The Company if found, otherwise None.
        """
        stmt = select(Company).where(Company.ticker == ticker.strip().upper())
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, ticker: str, name: str, sector: str | None = None, cik: str | None = None) -> Company:
        """Create a new company record.

        Args:
            ticker: Stock ticker symbol (will be uppercased).
            name: Company display name.
            sector: Optional industry sector.
            cik: Optional SEC EDGAR CIK identifier.

        Returns:
            The newly created Company.
        """
        company = Company(
            ticker=ticker.strip().upper(),
            name=name.strip(),
            sector=sector,
            cik=cik,
        )
        self._session.add(company)
        await self._session.flush()
        return company
